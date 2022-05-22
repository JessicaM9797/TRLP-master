### 一、实验说明
本实验用于模拟基于本地化差分隐私的时序位置发布算法(TRLP)，通过设计一种本地化的隐私机制对用户本地的时序数据进行隐私保护处理再上传。

### 二、实验数据集
实验采用两个数据集，分别是GeoLife 数据集和Gowalla数据集：
1. [GeoLife 数据集](https://www.microsoft.com/en-us/download/details.aspx?id=52367&from=http%3A%2F%2Fresearch.microsoft.com%2Fen-us%2Fdownloads%2Fb16d359d-d164-469e-9fd4-daa38f2b2e13%2F)
   记录了从2007年4月到2012年8月182个用户的轨迹数据，包含一系列以时间为序的包含经纬度、海拔等信息位置点信息，共计包含17621条轨迹。
2. [Gowalla数据集](http://snap.stanford.edu/data/loc-gowalla.html) 
   中包含196586名用户20个月内在6442890个位置上签到的数据。

### 三、实验环境
- python 3.7
- numpy 1.16.2

### 四、关键代码说明

 1. src/map_processor.py: 隐私策略图设计模块。
 2. src/mechanism.py: 设计两种本地化差分隐私机制，分别是传统的拉普拉斯机制(基线算法)和改进后的TRLP算法。
 3. src/mechanism_with_policy_graph: 将隐私策略图与本地化差分隐私机制结合。
 4. src/trajectory_processor.py 用于处理传入的时序位置数据集。

### 五、实验步骤
在test/test.ipynb中进行实验：
1. 导入GeoLife和Gowalla数据集并进行预处理。
2. 使用处理后的数据对马尔可夫状态转移矩阵进行训练。
3. 根据设定的四种隐私预算和三种隐私策略分别运行基线算法和TRLP算法。
4. 使用joblib.dump将实验结果进行保存。
5. 读取实验结果并生成结果图。
