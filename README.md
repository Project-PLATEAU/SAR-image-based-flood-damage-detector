# SAR衛星解析による洪水被害の推定システム

![概要](./img/tutorial_001.png)

## 1. 概要
本リポジトリでは、2023年度のProject PLATEAUが開発した「SAR衛星解析による洪水被害の推定システム」のソースコードを公開しています。  
「SAR衛星解析による洪水被害の推定システム」は、SAR衛星データを解析して洪水災害等の浸水範囲を解析する機能と、この解析結果と3D都市モデルを活用することで家屋の浸水被害の程度を推定する機能から構築されています。


## 2. 「SAR衛星解析による洪水被害の推定システム」について
SAR衛星データを解析して洪水災害等の浸水範囲を解析する機能は、機械学習モデルを用いて人工衛星観測データ（SARデータ）から浸水範囲を解析します。また、推定した浸水範囲と3D都市モデルの地形モデル及び建築物モデルを組合せることで、家屋単位での浸水深の算出および被災判定を行います。  
本システムの詳細については[技術検証レポート](https:XXX)を参照してください。

## 3. 利用手順
本システムの構築手順及び利用手順については[利用チュートリアル](https://project-plateau.github.io/SAR-image-based-flood-damage-detector/)を参照してください。  
本システムは実行環境としてGoogle Colaboratoryを想定しています。

## 4. システム概要
### 【人工衛星観測データの解析】
#### ⓪プロジェクトの初期・3D都市モデル（CityGML）の読み込み（0_PrepareProject.ipynb）
- 解析対象となるCityGMLと、対象エリアとなる領域の緯度・経度情報またはポリゴンデータを入力することで、CityGMLを解析して、対象エリアの建物データを生成し、日本の地理情報機関からデジタル標高モデル（DEM、5mメッシュ）を事前にダウンロードします。
- ここでは、GoogleDriveへの接続が必要となります。

#### ①SARデータの読み込み・SARデータによる浸水確率ラスターデータの推定（1_EstimateSAR-FloodPrbDiff.ipynb）
- 対象となる洪水日を指定することでその日の人工衛星観測データを、GoogleEarthEngineからSentinel-1の人工衛星観測データを取得し、これを利用して浸水学習モデルを使用して、浸水エリアを分類します。
- 出力は浸水確率ラスターデータであり、洪水時の人工衛星観測データとその前の人工衛星観測データの浸水確率の差を示しています。
- ここでは、GoogleDriveへの接続が必要となります。

#### ②浸水ポイントクラウドデータの生成（2_GeneratePointGroup.ipynb）
- 浸水確率ラスターデータで特定の閾値を超える確率の差があるピクセルを浸水に分類する。その後、ピクセルはグリッドシステムの違いを克服するために点群データを形成する多数のランダムポイントに変換される。
- ここでは、GoogleDriveへの接続が必要となります。
- 以下のパラメータ調整が可能です。

#### ③浸水面の高度ラスターデータと浸水深データの生成（3_CalcFloodDEMRaster.ipynb）
- 浸水ポイントクラウドデータから浸水面の高度ラスターデータと浸水深データを生成します。
- ここでは、GoogleDriveへの接続が必要となります。
- 以下のパラメータの調整が可能です。

#### ④建物への浸水深付与（4_AssessBuildings.ipynb）
- 建物データと浸水面の高度ラスターデータを使用して、建物の被災データ（CSV形式）を生成します。
- 各建物への浸水深は、DEM内の建物の位置と浸水レベルの高低差によって決定される。その後、建物は構造種別と浸水深に基づいて異なる被災カテゴリに分類され、床上浸水か床下浸水かどうかが判定される。
- ここでは、GoogleDriveへの接続が必要となります。

### 【解析結果のアップロード】
#### ⑤Re:Earth CMSへのアップロード（5_Upload.ipynb）
- 前項目で生成したデータを読み込み、データをRe:Earth CMSにアップロードします。
- ここでは、GoogleDriveへの接続・Re:Earth CMSとの認証が必要となります。

### 【プログラム】
#### DEMデータの補正用のプログラム（plateau_floodsar_lib.py）
- ⓪、③、④で呼び出されるプログラムです。
- 日本の地理情報機関からDEMタイルをダウンロードし、ローカルに保存。複数のタイプのDEMデータ（例：DEM5A、DEM5B）を統合し、ジオイド高さを計算し、指定されたエリアの値を抽出および補完します。

### 【GIAJ浸水エリアのGeoJSONファイルの分析（サブシーケンス）】
#### GIAJ GeoJSONから浸水面の高度ラスターデータの生成（s1-s3_GIAJ_FloodArea_Raster.ipynb）
- ローカルに保存されたJSONファイルで動作します。
- GIAJ GeoJsonから洪水面高度ラスターデータを生成します。
- メインステップ①〜③を代替します。
- このファイルを実行した後、メインステップ④で続行してください。
- ここでは、GoogleDriveへの接続が必要となります。

### 【ALOS-2の分析（サブシーケンス）】
#### ALOS-2の分析（s1_ALOS-2_EstimateSAR-FloodPrb.ipynb）
- ローカルに保存されたGeoTIFFファイルで動作します。ローカルのALOS-2 SARデータをGoogle Driveにアップロードし、tiff_pathの場所を指定してください。
- メインステップ①を代替します。
- このファイルを実行した後、メインステップ②で続行してください。
- ここでは、GoogleDriveへの接続が必要となります。
- 注意: このファイルはプロトタイプであるため、対象エリアはローカルのSAR TIFFファイルに含まれている必要があります。
- データを見つけるヒントについてはFindSARofJapan.mdを読んでください。

### 【ASNARO-2の分析（サブシーケンス）】
#### ASNARO-2の分析（s1-s2_ASNARO-2_EstimateSAR_FloodPrb.ipynb）
- ローカルに保存されたGeoTIFFファイルで動作します。
- メインステップ①～②を代替します。
- このファイルを実行した後、メインステップ③で続行してください。
- ここでは、GoogleDriveへの接続が必要となります。

## 5. 利用技術

| 種別              | 名称   | バージョン | 内容 |
| ----------------- | --------|-------------|-----------------------------|
| アプリケーション       | [Google Colaboratory](https://colab.research.google.com/?hl=ja) |  | Googleが提供するクラウドベースのJupyterノートブック環境 |
| ライブラリ | numpy | 1.23.5 | 数値情報処理の根幹ライブラリ |
|       | requests | 2.31.0 | APIアクセスに利用 |
|       | progressbar | 4.2.0 | 実行時間の予想と把握のためのライブラリ |
|       | matplotlib | 3.7.1 | グラフ描画ライブラリ |
|       | scipy | 1.11.4 | 数学、科学、工学分野の数値解析ライブラリ |
|       | ee | - | Google Earth Engine (GEE)を利用するためのライブラリ |
|       | PyTorch | 1.11.0 | Deep Learningフレームワーク（AIの構造定義や学習/判読処理のために使用） |
|       | torchvision | 0.16.0+cu121 | PyTorchプロジェクトに含まれているパッケージ |
|       | MLFlow | 1.26.1 | AI実験管理用ライブラリ（AI学習結果・学習時設定パラメータ管理に使用） |
|       | pyproj | 3.6.1 | 座標変換用のライブラリ |
|       | rasterio | 1.3.9 | 地理空間情報画像操作ライブラリ（変化検出結果からGISデータへの変換に使用） |
|       | sklearn | 1.2.2 | 機械学習のライブラリ |
|       | skimage | 0.19.3 | 画像処理/機械学習ライブラリ（AIに入力するための画像加工に使用） |
|       | [plateauutils](https://github.com/eukarya-inc/plateauutils) | 0.0.14 | PLATEAUの3D都市モデルのパーサのライブラリ |
|       | [reearthcmsapi](https://github.com/eukarya-inc/reearth-cms-api) | 0.0.3 | Re:Earth CMSへのアップロードを行うライブラリ |

## 6. 動作環境 <!-- 動作環境についての仕様を記載ください。 -->
- Google Colaboratoryでの動作を前提としています。

| 項目               | GoogleColaboratoryでの動作環境（2024/02/01時点） | 推奨環境 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| CPU                | コア数2，スレッド数4    | 同左 |
| GPU                | Tesla K80 GPU等        | 同左 |
| メモリ             | 12.7GB以上             | 同左 |
| ネットワーク       | クラウド型サービスのためネットワーク環境は必要 | 同左 |
## 7. 本リポジトリのフォルダ構成 <!-- 本GitHub上のソースファイルの構成を記載ください。 -->
| フォルダ名 |　詳細 |
|-|-|
| PLATEAU-FloodSAR | GoogleColaboratoryのPythonコードが格納されたフォルダ |
| boundary_sample | 解析対象範囲のサンプルとして久留米市のファイルが格納されているフォルダ |
| img | README.mdの画像が格納されたフォルダ |

## 8. ライセンス

- ソースコード及び関連ドキュメントの著作権は国土交通省に帰属します。
- 本ドキュメントは[Project PLATEAUのサイトポリシー](https://www.mlit.go.jp/plateau/site-policy/)（CCBY4.0及び政府標準利用規約2.0）に従い提供されています。

## 9. 注意事項

- 本リポジトリは参考資料として提供しているものです。動作保証は行っていません。
- 本リポジトリについては予告なく変更又は削除をする可能性があります。
- 本リポジトリの利用により生じた損失及び損害等について、国土交通省はいかなる責任も負わないものとします。

## 10. 参考資料
- 技術検証レポート: https:XXX
- PLATEAU WebサイトのUse caseページ「人工衛星観測データを用いた浸水被害把握」: https://www.mlit.go.jp/plateau/use-case/uc23-01/
