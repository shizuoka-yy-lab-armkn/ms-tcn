# MS-TCN for [FIELDS-public](https://github.com/shizuoka-yy-lab-armkn/FIELDS-public)

## :warning: Note :warning:

- This repository is forked from [yabufarha/ms-tcn](https://github.com/yabufarha/ms-tcn) .
- This repository is for learning models used in [FIELDS-public](https://github.com/shizuoka-yy-lab-armkn/FIELDS-public) .


## Training
1. Download `mstcn_train_dataset_motorcycle_blip2_features.tar.gz` from https://drive.google.com/drive/folders/10pHmn2Qg8ZJ08SQyfsvvi0krTDzzfHpQ?usp=sharing

2. Extract it and rename to `data/motorcycle_blip2_features`

    ```bash
    .
    ├── LICENSE
    ├── Makefile
    ├── README.md
    ├── data/
    │   ├── motorcycle_blip2_features/ # ← Here!!
    ├── mstcn/
    │   ├── batch_gen.py
    │   ├── eval.py
    │   ├── main.py
    │   └── model.py
    ├── poetry.Darwin.lock
    ├── poetry.Linux.lock
    └── pyproject.toml
    ```

3. Install dependencies

    ```bash
    make install
    ```

3. Run training.

    ```bash
    python3 -m mstcn.main --action=train --dataset=motorcycle_blip2_features --split=101
    ```

    `--split=101` specifies the split number.
    A *split* refers to the partitioning of the dataset into training and test data.
    When `101` is specified, `data/motorcycle_blip2_features/train101.bundle` will be used.

### Prediction:

```bash
python3 -m mstcn.main --action=predict --dataset=motorcycle_blip2_features --split=101
```

### Evaluation:

```
python3 -m mstcn.eval --dataset=motorcycle_blip2_features --split=101
```

### Citation:

If you use the code, please cite

    Y. Abu Farha and J. Gall.
    MS-TCN: Multi-Stage Temporal Convolutional Network for Action Segmentation.
    In IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2019

    S. Li, Y. Abu Farha, Y. Liu, MM. Cheng,  and J. Gall.
    MS-TCN++: Multi-Stage Temporal Convolutional Network for Action Segmentation.
    In IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI), 2020
