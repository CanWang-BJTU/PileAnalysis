# 基于 m 法的桩基分析程序介绍
# 欢迎使用本程序👏
# 下载链接 : https://www.yunpan.com/surl_yNkjFKKBVwU （提取码：9e6b）

## 1. 主界面介绍

<img src="https://github.com/user-attachments/assets/9cdc17c6-612c-4bce-b74c-5f84766fcdc9" width="80%" />

打开主界面后，界面主要分为两个区域：
* **左侧**：计算结果展示和可视化展示区域。
* **右侧**：模式选择和参数输入区。

## 2. 工况选择

<img width="1326" height="242" alt="image" src="https://github.com/user-attachments/assets/252099d9-50a0-4986-bc8d-4e7c096f7a5f" />


本程序提供两种工况模式：
1.  **从现有工况计算**：适用于已有 `.dat` 文件的情况。
2.  **新建工况**：适用于无 `.dat` 文件的情况。

### 2.1 现有工况计算介绍

点击【现有工况】后，右侧将跳转至现有工况计算菜单界面：

<img width="1332" height="300" alt="image" src="https://github.com/user-attachments/assets/fd518fde-33d7-4d78-96ff-9a635d34cc7a" />

点击【导入现有的dat文件】：

<img width="1332" height="472" alt="image" src="https://github.com/user-attachments/assets/a0c8de3b-d08a-4aa3-96ba-39747a38d9bf" />

这样程序会自动识别已有dat文件的的计算模式，以及相关参数，自动勾选相对应的模式，点击直接计算就可以进行相关分析和可视化。

另外用户可以手动点击模式，切换到需要的模式。（注：【模式2：反算】，需要手动点击查看与计算，输入承台中心位移参数，点击【模式4：单桩刚度计算】，会自动弹出桩位布置界面，用户需要手动选择计算的桩号）

若参数需要修改，我们点击【查看与修改】按钮，弹出详细的参数修改页面：

<img width="1352" height="1056" alt="image" src="https://github.com/user-attachments/assets/bd7de3dc-478e-4f8c-bbc1-58b394ee1557" />

<img width="1368" height="1038" alt="image" src="https://github.com/user-attachments/assets/c1834674-6238-421c-be27-23924b25496b" />

<img width="1336" height="948" alt="image" src="https://github.com/user-attachments/assets/cb259433-36a0-4560-9a26-5cfc94eb348d" />

关于各个参数此处不过多赘述，点击相关参数旁边【 ？】按钮，则可以弹出相关参数的参考值与介绍。

特别的，点击菜单栏【帮助】按钮，这里汇总了所有参数的参考值与介绍

<img width="1674" height="1234" alt="image" src="https://github.com/user-attachments/assets/9faeca78-f57e-463e-ae66-37e5e36134c2" />


本程序还提供保存导出工况功能，点击【保存并导出】就可以导出已经编辑好了的工况.dat文件

### 2.2 新建工况介绍

新建工况整体同现有工况，操作逻辑为先选择模式，弹出对应参数输入界面，输入界面与「现有工况」模式一致，同样提供保存新建工况功能。

<img width="1346" height="1418" alt="image" src="https://github.com/user-attachments/assets/933ed0c9-a2fd-48b1-b076-af03b3b4bc17" />

## 3. 各个模式介绍

详细见仓库中的example，此处不过多赘述

## 4.绘图区域介绍

### 4.1 原理图

<img width="1664" height="1080" alt="image" src="https://github.com/user-attachments/assets/19dee094-bf79-4b41-8180-fec057f57e7b" />

再未开始计算的时候展示原理图，方便用户快速了解各个输入参数，输入顺序。

### 4.2 计算完成后的可视化

#### 4.2.1 模式一和模式二

模式一和模式二提供3D桩布位置图，2D平面载荷图，各桩桩身响应图

<img width="1606" height="990" alt="image" src="https://github.com/user-attachments/assets/edddc3c0-0f6f-49d3-a2c7-ad84b60e0ebf" />

<img width="1612" height="994" alt="image" src="https://github.com/user-attachments/assets/c379b833-2cfd-4ac9-9d94-6c2db76b018d" />

<img width="1626" height="1002" alt="image" src="https://github.com/user-attachments/assets/0840a568-1e10-42f0-ab7e-de66d20b7dbd" />

其中桩身响应图明确指出最不利桩，每根桩的最大位移，轴力，弯矩及其位置。

用户可以使用toolbar中的导出功能，实行多种格式的图片输出，适应多种类二次开发和加工。

#### 4.2.2 模式三和模式四

模式三和模式四只提供3D桩布位置图，2D平面图，相关展示同4.2.1

## 5.结果输出区介绍

<img width="1652" height="120" alt="image" src="https://github.com/user-attachments/assets/c0a231c9-e458-4338-9383-235ed3435108" />

提供结果摘要和原始结果。详细的各个模式结果输出介绍见仓库中example

## 6.特色功能

<img width="562" height="276" alt="image" src="https://github.com/user-attachments/assets/85b07561-253e-41e8-a208-063dcfa1cc4a" />

点击菜单栏中【导出】按钮，支持一键导出【结果摘要.txt】，【原始输出.txt】,【所有图片】,【刚度矩阵.csv】

特别的【刚度矩阵.csv】中既有z轴向下的刚度矩阵，也有z轴向上的刚度矩阵，方便与sap2000等商业软件交互。
















