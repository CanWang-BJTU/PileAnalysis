# 基于 m 法的桩基分析程序 
# 最近更新日期2026年2月4日 最新版本 V2.2.3 建议更新下载
# 点击右侧Release下载最新版本
## 修复若干细节问题。最新版优化载荷输入逻辑，支持载荷位置定义，多载荷同时作用分析。优化了模拟桩输入逻辑，支持模拟桩位置自定义，提供全量矩阵以及对角线刚度矩阵两种输入方式。优化3D绘图，方便用户直观感受桩基布置情况，桩基倾斜角度以及桩基截面形状。优化平面载荷图显示效果。

## 欢迎使用本程序！👋 本软件旨在为工程人员提供便捷、可视化的桩基分析工具。

## 教程


点击顶部菜单栏【教程】按钮，弹出下拉菜单，里边有对应三个模式的教程以及pile说明书中的示例，即可填充进GUI界面，用户可以以例子为模版，进行修改，保存，运行等等。教程中还提供每个算例的说明解析。

<p align="center">
  <img src="https://github.com/user-attachments/assets/71c45a20-c961-47cc-a39e-e5e311e76bfd" width="45%" />
  <img src="https://github.com/user-attachments/assets/54d4d6cc-6bbc-4c75-ae0f-3fc85ccd7fae" width="45%" />
</p>
<p align="center">
  <img src="https://github.com/user-attachments/assets/fae5cba6-608b-47e2-af98-b0d0baef7780" width="60%" />
</p>

## 1. 主界面介绍

<img width="3022" height="1802" alt="image" src="https://github.com/user-attachments/assets/cfc9a2fa-51fa-4dda-9dc5-23b552c9ea4d" />


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

<img width="1192" height="304" alt="image" src="https://github.com/user-attachments/assets/d1c7779e-fd40-448b-869c-0f9d1a82b769" />

接下来点击 **【导入现有的dat文件】**：

<img width="1312" height="290" alt="image" src="https://github.com/user-attachments/assets/6a656c60-ef98-47ce-8e07-6e6fe1c7d6a0" />


**智能化导入逻辑：**
程序会自动解析 `.dat` 文件，识别计算模式及相关参数，并自动勾选对应的分析模式。通常情况下，点击 **【直接计算】** 即可完成分析与可视化。

> **注意：特殊模式说明**
> * 用户也可手动切换模式，修改相关参数再进行计算
> * **模式 4（单桩刚度计算）**：选择该模式后会自动弹出桩位布置界面，用户需手动指定计算的桩号。

**参数修改：**
若需微调参数，点击 **【查看与修改】** 按钮，即可弹出详细参数编辑页面，这里以模式3为例子：

<p align="center">
  <img src="https://github.com/user-attachments/assets/62bb31ed-ca66-4936-9747-71afaa5f738f" width="45%" />
  <img src="https://github.com/user-attachments/assets/14135838-c1d9-47a0-8bb8-73dd24b68e96" width="45%" />
</p>
<p align="center">
  <img src="https://github.com/user-attachments/assets/b89cfd5a-edf1-491f-8604-a1fed2f5894f" width="60%" />
</p>

**帮助系统：**
* **即时提示**：点击参数旁的 **【？】** 按钮，可查看该参数的推荐取值与物理含义。
* **完整文档**：点击菜单栏 **【帮助】**，可查看所有参数的汇总说明。

<img src="https://github.com/user-attachments/assets/9faeca78-f57e-463e-ae66-37e5e36134c2" width="60%" />

**关于模拟桩输入：**

<img width="1156" height="790" alt="image" src="https://github.com/user-attachments/assets/c54b7657-de16-4d23-aa7b-5f0c8ca0dc96" />

> * 模拟桩输入可以定义模拟桩位置
> * 提供模拟桩两种刚度输入方式，全量矩阵和对角线刚度两种，方便用户选择


**保存功能：**
编辑完成后，点击 **【保存并导出】** 即可生成新的 `.dat` 工况文件。

### 2.2 新建工况

<img width="1194" height="264" alt="image" src="https://github.com/user-attachments/assets/a24d1789-2908-4b14-8c75-16ca9c96bdf7" />



新建工况的操作逻辑与“现有工况”类似。用户需先选择计算模式，随后程序会弹出对应的参数输入界面。输入完成后，同样支持保存为工况文件。

---

## 3. 各个模式介绍

本程序包含多种计算模式（如群桩刚度、单桩刚度、桩基反算等）。
* 详细的模式说明与输入输出示例，请参阅程序中【教程】。

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
  <img src="https://github.com/user-attachments/assets/32775224-a95f-4a3a-8b6d-4ea79fee24c7" width="32%" />
  <img src="https://github.com/user-attachments/assets/b0a09367-6d1b-432a-9ea5-e62fb4c4cc11" width="32%" />
  <img src="https://github.com/user-attachments/assets/3737b4c1-c302-4c7c-9b33-2a0ef9ddd4ee" width="32%"/>

</p>

**关键特性：**
* **智能识别最不利桩**：3D绘图能够直观展示桩基布置情况以及截面类型
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
* 更详细的输出格式说明，请参考【教程。

---

## 6. 特色功能：一键导出

<img src="https://github.com/user-attachments/assets/85b07561-253e-41e8-a208-063dcfa1cc4a" width="40%" />

点击菜单栏中的 **【导出】** 按钮，支持一键生成以下文件：

* `所有图片以及结果摘要` 
* `所有可视化图片` (批量导出)
*  **`刚度矩阵.csv`**
*  **`结果摘要.csv`**

> **刚度矩阵特别说明**
> 导出的 `.csv` 文件中包含 **z 轴向下** 和 **z 轴向上** 两种坐标系下的刚度矩阵，可直接用于与 **SAP2000** 等商业结构分析软件进行交互对接，极大提升工作效率。
