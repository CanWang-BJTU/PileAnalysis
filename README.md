# 基于 m 法的桩基分析程序（V2.0.1）

欢迎使用本程序！👋 本软件旨在为工程人员提供便捷、可视化的桩基分析工具。

## 1. 主界面介绍

<img src="https://github.com/user-attachments/assets/9cdc17c6-612c-4bce-b74c-5f84766fcdc9" width="100%" />

打开软件后，主界面布局逻辑清晰，主要分为两个区域：
* **左侧：可视化与结果区**
    * 负责展示计算结果的数据摘要。
    * 提供交互式的可视化绘图展示。
* **右侧：控制与输入区**
    * 负责工况模式的选择。
    * 提供参数输入的交互界面。

---

## 2. 工况选择

<img src="https://github.com/user-attachments/assets/252099d9-50a0-4986-bc8d-4e7c096f7a5f" width="80%" />

本程序提供两种工况建立模式，满足不同场景需求：
1.  **从现有工况计算**：适用于已有 `.dat` 数据文件的情况，支持快速导入复算。
2.  **新建工况**：适用于无 `.dat` 文件的情况，从零开始建立模型。

### 2.1 现有工况计算

点击右侧的 **【现有工况】** 按钮，界面将跳转至计算菜单：

<img src="https://github.com/user-attachments/assets/fd518fde-33d7-4d78-96ff-9a635d34cc7a" width="80%" />

接下来点击 **【导入现有的dat文件】**：

<img src="https://github.com/user-attachments/assets/a0c8de3b-d08a-4aa3-96ba-39747a38d9bf" width="80%" />

**智能化导入逻辑：**
程序会自动解析 `.dat` 文件，识别计算模式及相关参数，并自动勾选对应的分析模式。通常情况下，点击 **【直接计算】** 即可完成分析与可视化。

> **注意：特殊模式说明**
> * 用户也可手动切换模式。
> * **模式 2（反算）**：需手动点击【查看与计算】，输入承台中心位移参数。
> * **模式 4（单桩刚度计算）**：选择该模式后会自动弹出桩位布置界面，用户需手动指定计算的桩号。

**参数修改：**
若需微调参数，点击 **【查看与修改】** 按钮，即可弹出详细参数编辑页面：

<p align="center">
  <img src="https://github.com/user-attachments/assets/bd7de3dc-478e-4f8c-bbc1-58b394ee1557" width="45%" />
  <img src="https://github.com/user-attachments/assets/c1834674-6238-421c-be27-23924b25496b" width="45%" />
</p>
<p align="center">
  <img src="https://github.com/user-attachments/assets/cb259433-36a0-4560-9a26-5cfc94eb348d" width="60%" />
</p>

**帮助系统：**
* **即时提示**：点击参数旁的 **【？】** 按钮，可查看该参数的推荐取值与物理含义。
* **完整文档**：点击菜单栏 **【帮助】**，可查看所有参数的汇总说明。

<img src="https://github.com/user-attachments/assets/9faeca78-f57e-463e-ae66-37e5e36134c2" width="60%" />

**保存功能：**
编辑完成后，点击 **【保存并导出】** 即可生成新的 `.dat` 工况文件。

### 2.2 新建工况

<img src="https://github.com/user-attachments/assets/933ed0c9-a2fd-48b1-b076-af03b3b4bc17" width="60%" />

新建工况的操作逻辑与“现有工况”类似。用户需先选择计算模式，随后程序会弹出对应的参数输入界面。输入完成后，同样支持保存为工况文件。

---

## 3. 各个模式介绍

本程序包含多种计算模式（如正算、反算、刚度计算等）。
* 详细的模式说明与输入输出示例，请参阅仓库中的 `example` 文件夹。

---

## 4. 绘图区域介绍

### 4.1 原理图展示

<img src="https://github.com/user-attachments/assets/19dee094-bf79-4b41-8180-fec057f57e7b" width="80%" />

在未开始计算前，绘图区展示计算原理图，帮助用户快速理解参数含义及输入顺序。

### 4.2 计算结果可视化

#### 4.2.1 模式一和模式二
提供全方位的可视化支持，包括：
* 3D 桩位布置图
* 2D 平面载荷图
* **各桩桩身响应图**

<p align="center">
  <img src="https://github.com/user-attachments/assets/edddc3c0-0f6f-49d3-a2c7-ad84b60e0ebf" width="32%" />
  <img src="https://github.com/user-attachments/assets/c379b833-2cfd-4ac9-9d94-6c2db76b018d" width="32%" />
  <img src="https://github.com/user-attachments/assets/0840a568-1e10-42f0-ab7e-de66d20b7dbd" width="32%" />
</p>

**关键特性：**
* **智能识别最不利桩**：桩身响应图明确标注出最不利桩的位置。
* **关键指标展示**：直观展示最大位移、轴力、弯矩及其发生位置。
* **多格式导出**：通过 Toolbar 工具栏，支持导出多种格式的图片，方便二次开发或撰写报告。

#### 4.2.2 模式三和模式四
* 提供 3D 桩位布置图及 2D 平面图。
* 相关展示交互功能同上。

---

## 5. 结果输出区介绍

<img src="https://github.com/user-attachments/assets/c0a231c9-e458-4338-9383-235ed3435108" width="80%" />

计算完成后，界面左侧提供**结果摘要**和**原始结果**预览。
* 更详细的输出格式说明，请参考 `example` 文件夹。

---

## 6. 特色功能：一键导出

<img src="https://github.com/user-attachments/assets/85b07561-253e-41e8-a208-063dcfa1cc4a" width="40%" />

点击菜单栏中的 **【导出】** 按钮，支持一键生成以下文件：

* `结果摘要.txt`
* `原始输出.txt`
* `所有可视化图片` (批量导出)
*  **`刚度矩阵.csv`**

> **刚度矩阵特别说明**
> 导出的 `.csv` 文件中包含 **z 轴向下** 和 **z 轴向上** 两种坐标系下的刚度矩阵，可直接用于与 **SAP2000** 等商业结构分析软件进行交互对接，极大提升工作效率。
