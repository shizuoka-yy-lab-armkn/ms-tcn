from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import optim

from mstcn.batch_gen import BatchGenerator


class MultiStageModel(nn.Module):
    def __init__(self, num_stages, num_layers, num_f_maps, dim, num_classes):
        super().__init__()
        self.stage1 = SingleStageModel(num_layers, num_f_maps, dim, num_classes)
        self.stages = nn.ModuleList(
            SingleStageModel(num_layers, num_f_maps, num_classes, num_classes)
            for _ in range(num_stages - 1)
        )

    def forward(self, x, mask):
        out = self.stage1(x, mask)
        outputs = out.unsqueeze(0)
        for s in self.stages:
            out = s(F.softmax(out, dim=1) * mask[:, 0:1, :], mask)
            outputs = torch.cat((outputs, out.unsqueeze(0)), dim=0)
        return outputs


class SingleStageModel(nn.Module):
    def __init__(self, num_layers, num_f_maps, dim, num_classes):
        super().__init__()
        self.conv_1x1 = nn.Conv1d(dim, num_f_maps, 1)
        self.layers = nn.ModuleList(
            DilatedResidualLayer(2**i, num_f_maps, num_f_maps)
            for i in range(num_layers)
        )
        self.conv_out = nn.Conv1d(num_f_maps, num_classes, 1)

    def forward(self, x, mask):
        out = self.conv_1x1(x)
        for layer in self.layers:
            out = layer(out, mask)
        out = self.conv_out(out) * mask[:, 0:1, :]
        return out


class DilatedResidualLayer(nn.Module):
    def __init__(self, dilation, in_channels, out_channels):
        super().__init__()
        self.conv_dilated = nn.Conv1d(
            in_channels, out_channels, 3, padding=dilation, dilation=dilation
        )
        self.conv_1x1 = nn.Conv1d(out_channels, out_channels, 1)
        self.dropout = nn.Dropout()

    def forward(self, x, mask):
        out = F.relu(self.conv_dilated(x))
        out = self.conv_1x1(out)
        out = self.dropout(out)
        return (x + out) * mask[:, 0:1, :]


class Trainer:
    def __init__(self, num_blocks, num_layers, num_f_maps, dim, num_classes):
        self.model = MultiStageModel(
            num_blocks, num_layers, num_f_maps, dim, num_classes
        )
        self.ce = nn.CrossEntropyLoss(ignore_index=-100)
        self.mse = nn.MSELoss(reduction="none")
        self.num_classes = num_classes

    def train(
        self,
        save_dir: Path,
        *,
        batch_gen_train: BatchGenerator,
        batch_gen_test: BatchGenerator,
        num_epochs: int,
        batch_size: int,
        learning_rate: float,
        device: torch.device,
    ):
        self.model.to(device)

        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)

        for epoch in range(num_epochs):
            self.model.train()
            train_epoch_loss = 0
            train_correct = 0
            train_total = 0
            while batch_gen_train.has_next():
                batch_input, batch_target, mask = batch_gen_train.next_batch(batch_size)
                batch_input, batch_target, mask = (
                    batch_input.to(device),
                    batch_target.to(device),
                    mask.to(device),
                )
                optimizer.zero_grad()
                predictions = self.model(batch_input, mask)

                loss = torch.tensor(0.0, device=device)
                for p in predictions:
                    loss += self.ce(
                        p.transpose(2, 1).contiguous().view(-1, self.num_classes),
                        batch_target.view(-1),
                    )
                    loss += 0.15 * torch.mean(
                        torch.clamp(
                            self.mse(
                                F.log_softmax(p[:, :, 1:], dim=1),
                                F.log_softmax(p.detach()[:, :, :-1], dim=1),
                            ),
                            min=0,
                            max=16,
                        )
                        * mask[:, :, 1:]
                    )

                train_epoch_loss += loss.item()
                loss.backward()
                optimizer.step()

                _, predicted = torch.max(predictions[-1].data, 1)
                train_correct += (
                    ((predicted == batch_target).float() * mask[:, 0, :].squeeze(1))
                    .sum()
                    .item()
                )
                train_total += torch.sum(mask[:, 0, :]).item()

            batch_gen_train.reset()
            torch.save(self.model.state_dict(), save_dir / f"epoch-{epoch + 1}.model")
            torch.save(optimizer.state_dict(), save_dir / f"epoch-{epoch + 1}.opt")

            self.model.eval()
            test_epoch_loss = 0
            test_correct = 0
            test_total = 0
            with torch.no_grad():
                while batch_gen_test.has_next():
                    batch_input, batch_target, mask = batch_gen_test.next_batch(
                        batch_size
                    )
                    batch_input, batch_target, mask = (
                        batch_input.to(device),
                        batch_target.to(device),
                        mask.to(device),
                    )
                    predictions = self.model(batch_input, mask)

                    loss = torch.tensor(0.0, device=device)
                    for p in predictions:
                        loss += self.ce(
                            p.transpose(2, 1).contiguous().view(-1, self.num_classes),
                            batch_target.view(-1),
                        )
                        loss += 0.15 * torch.mean(
                            torch.clamp(
                                self.mse(
                                    F.log_softmax(p[:, :, 1:], dim=1),
                                    F.log_softmax(p.detach()[:, :, :-1], dim=1),
                                ),
                                min=0,
                                max=16,
                            )
                            * mask[:, :, 1:]
                        )

                    test_epoch_loss += loss.item()

                    _, predicted = torch.max(predictions[-1].data, 1)
                    test_correct += (
                        ((predicted == batch_target).float() * mask[:, 0, :].squeeze(1))
                        .sum()
                        .item()
                    )
                    test_total += torch.sum(mask[:, 0, :]).item()

                batch_gen_test.reset()

            print(
                "[epoch %03d]: trainLoss=%.4f, trainAcc=%.4f ;; testLoss=%.4f, testAcc=%.4f"
                % (
                    epoch + 1,
                    train_epoch_loss / len(batch_gen_train.list_of_examples),
                    train_correct / train_total,
                    test_epoch_loss / len(batch_gen_test.list_of_examples),
                    test_correct / test_total,
                )
            )

    def predict(
        self,
        model_dir: Path,
        results_dir: Path,
        features_dir: Path,
        vid_list_file: Path,
        epoch: int,
        actions_dict: dict[str, int],
        device: torch.device,
        sample_rate: int,
    ) -> None:
        self.model.eval()
        actions_dict_inv = {
            act_id: act_name for act_name, act_id in actions_dict.items()
        }
        with torch.no_grad():
            self.model.to(device)
            self.model.load_state_dict(torch.load(model_dir / f"epoch-{epoch}.model"))

            with open(vid_list_file, "r") as f:
                list_of_vids = [line.strip() for line in f.readlines()]

            for vid in list_of_vids:
                print(vid)
                features = np.load(features_dir / (vid.split(".")[0] + ".npy"))
                features = features[:, ::sample_rate]
                input_x = torch.tensor(features, dtype=torch.float)
                input_x.unsqueeze_(0)
                input_x = input_x.to(device)
                predictions = self.model(
                    input_x, torch.ones(input_x.size(), device=device)
                )
                _, predicted = torch.max(predictions[-1].data, 1)
                predicted = predicted.squeeze()
                recognition = []
                for i in range(len(predicted)):
                    recognition = np.concatenate(
                        (
                            recognition,
                            [actions_dict_inv[int(predicted[i].item())]] * sample_rate,
                        )
                    )
                f_name = Path(vid).stem + ".txt"
                with open(results_dir / f_name, "w") as f:
                    f.write("\n".join(recognition))
                    f.write("\n")
