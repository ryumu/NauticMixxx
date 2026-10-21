# リアルタイム音声処理・負荷調査

対象: 作業ツリーのMixxx 2.5.6 + NauticMixxxの変更（0056のバックグラウンド波形準備を含む）。
実装の変更は行わず、コード調査、既存テスト、実装を呼び出す追加計測を実施した。

## 修正状況（2026-10-22）

以下の本文・表は修正前の調査記録。対処を項目ごとに追加している。

- **0057: ECHO解除の一括消去を解消。** 履歴の有効範囲を管理し、リセット後に
  上書きされていない領域を無音として扱う。前回の音を復活させずに定数時間で無効化する。
  同じPiの追加計測（1000回）で、96 kHz状態の解除平均は0.651 msから0.00246 msへ、
  p99は2.022 msから0.00483 msへ減少した。別実行間の比較でありOS変動も含む。
  ECHOのゼロ消去参照との音声比較、既存Beat FX / Smart CFX、EngineBuffer / Mixerの
  ネイティブ検証69件がすべて成功。今回再ビルドしたテストでは以前の任意GUIクラッシュも再現せず通過。
  Windows予防チェック、57パッチの公式ソースへの適用・生成一致も確認した。
  ログ: `build/audio-fixes/0057/`。
- **0058: USB先読みの検証をまとめ、優先順位と中断を追加。** 最初の1曲を先に公開した後、
  最大16曲の前後でPDBを検証する。ANLZ作業は曲間で約8msの予算を確認し、ロード要求や
  一覧切り替え時には次の曲へ進まず譲る。1ファイルのI/O時間やPDB検証時間の上限ではない。
  解析済みメタデータの先読みはI/Oなしで再利用し、明示ロード・波形実体の検証は維持する。
  1000曲の同じ合成条件で13.656秒 / 1,052.10 MBから0.977秒 / 66.71 MBへ減少。
  バッチ化による削減であり、PDBサイズに依存する検証が完全に定数時間になるわけではない。
  USB関連139件成功・34件skip、Windows予防チェックと58パッチの生成一致を確認。
  ログ: `build/audio-fixes/0058/`。

## 結論

通常の2デッキ再生の計算量は小さい。一方、短いバッファでのキー固定、ECHO解除時の
大きなメモリ消去、ブラウザのバックグラウンド解析の読み取り増幅に対策の余地がある。
曲ロードやUSB保存では、画面スレッドが待たされる経路も残っている。

これは音切れを実際の出力機器で確認した報告ではない。音声デバイスの設定は変更せず、
ミキサーの処理時間とI/O量を測定した。Windows・macOS・物理USBの低速化や取り外し、
実画面のGPU描画、録音を併用する長時間の出力試験は未実施。

## 検証環境と方法

- Raspberry Pi 5 Model B Rev 1.1、Linux aarch64、Qt 6.8.2、Release / GCC 14。
- CPU governorは既存の `ondemand` のまま。測定中に2.4 GHzを確認したが、周波数固定や
  CPU占有は行っていない。通常優先度のテストプロセスであり、音声デバイスのRTスレッドとは異なる。
- ネイティブソース: `build/test-candidate/2.0.0-linux-aarch64/mixxx-2.5.6`。
  既存の `native/mixxx-test` とビルド済みオブジェクトを利用した追加実行ファイルで測定。
- 2デッキ試験: 実際のWAVデコーダー、CachingReader、EngineBuffer、EngineMixerを通す。
  `sine-30.wav` をUSB由来のTrackとして2デッキにロードし、キャッシュが温まった1秒区間を
  ループする。緊急再生用PCMキャプチャも動作する。メイン出力に信号があることを検査した。
- 出力48 kHz。キー固定ONはRubberBand Faster、速度変更は約+4%。各条件で100回の
  ウォームアップ後、1000コールバックを実時間間隔で実行し、ミキサー呼び出しの経過時間を測定。
  スリープ時間は計測値に含めない。GUIイベント処理、PortAudio、実機出力、録音は含めない。
- DSP単体試験: 実際のEchoEffect / EchoGroupState / Rx3EmergencyLoopを使用。
- USB試験: 100曲と1000曲の合成DeviceSQL/ANLZをローカルの一時ディレクトリに作成し、
  実際の `RekordboxUsbSession::loadTrackAnalysis()` を呼び出す。
  `/proc/self/io` の `rchar` 差分はキャッシュを含むプロセスの論理読み取り量であり、
  物理USBから転送されたバイト数ではない。PDB以外の検証用ファイルの読み取りも含む。

## 1. キー固定時は平均値より処理時間の山が問題になる

単位はms。p99は1000回のうち遅い約1%との境界。期限はフレーム数 / 48000。

| フレーム | キー固定 | 平均 | p99 | 最大 | 期限 | 期限超過 / 1000回 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 64 | OFF | 0.016 | 0.108 | 0.155 | 1.333 | 0 |
| 64 | ON | 0.199 | 1.662 | 3.791 | 1.333 | 28 |
| 128 | OFF | 0.034 | 0.337 | 0.574 | 2.667 | 0 |
| 128 | ON | 0.413 | 2.365 | 3.529 | 2.667 | 7 |
| 256 | OFF | 0.048 | 0.312 | 5.629 | 5.333 | 1 |
| 256 | ON | 0.794 | 3.553 | 6.055 | 5.333 | 1 |
| 512 | OFF | 0.072 | 0.427 | 0.516 | 10.667 | 0 |
| 512 | ON | 1.529 | 3.692 | 6.125 | 10.667 | 0 |

64/128フレームではキー固定によって遅い回が増える。通常再生の平均負荷だけで安全性を
判断できない。256フレームの通常再生にも外れ値があり、経過時間にはOSのスケジューリングも
含まれるため、全超過をDSPの純粋なCPU計算時間に帰属させることはできない。

このPiで安定性を優先して実機検証を始めるなら、今回超過のなかった512フレーム / 48 kHzを
出発点にし、実際のASIO/ALSA等の出力、FX、ブラウズ、録音を併用して短くできるか確認する。
512フレームは1処理分の時間であり、機器を含む総往復レイテンシーではない。
SoundTouchやRubberBand Finerとの性能比較は今回実施していない。

関連: `src/engine/enginebuffer.cpp:1060` 付近のスケーラー設定・実行、
`src/engine/bufferscalers/enginebufferscalerubberband.cpp`。

## 2. ECHO解除時に音声スレッドで数MiBを一括消去する（優先度: 高）

`EchoEffect::processChannel()` は `EffectEnableState::Disabling` のとき、
通常の1バッファ処理に加えて `delay_buf.clear()` を実行する。
0038で最大ディレイを3秒から6秒に増やしており、消去量も増えている。

| 状態の確保レート | バッファサイズ | 通常処理の平均 | 解除処理の平均 | 解除処理p99 | 解除処理最大 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 48 kHz | 約2.20 MiB | 0.002 ms | 0.250 ms | 0.321 ms | 0.379 ms |
| 96 kHz | 約4.39 MiB | 0.002 ms | 0.651 ms | 2.022 ms | 2.422 ms |

いずれも256フレーム、各状態1000回。解除状態を繰り返し直接呼ぶ単体試験であり、
アプリで毎回消去され続けるという意味ではない。実機の単発操作時のキャッシュ状態とも異なる。

`EngineEffect` は起動・ロード時に96 kHzで状態を事前作成する。
確認したECHO経路では、再生サンプルレートだけでこの確保サイズが自動縮小する処理はない。
そのため、出力48 kHzでも約4.39 MiBの消去が関係しうる。
ヘッドホンとメイン、複数デッキや複数ECHOの状態を同時に解除すれば処理が積み上がる。
その全経路を同時に解除するミキサー全体の時間は今回未測定。

対処案: 古いディレイを再利用しないことを保ちつつ、消去を小分けにする、
書き込み済み範囲・世代を管理するなどして、音声コールバック1回の消去量を制限する。
単にclearを削除すると前回の音が戻るため、その変更だけでは不十分。

関連: `src/effects/backends/builtin/echoeffect.cpp:242` 付近、同 `echoeffect.h:15`、
`src/engine/effects/engineeffect.cpp:13` / `:43`。
保守元: [0038](../patches/0038-rx3-beatfx-audio-and-controls.patch)。

## 3. バックグラウンド解析の読み取り量が曲数とともに急増する（優先度: 高）

0056は一覧を開いた後、その一覧全体のANLZ検査を1曲ずつ進める。
ワーカーは1つに制限されているが、`loadTrackAnalysis()` はキャッシュ再利用時も
最初に `refresh()` を呼び、`inspectDevice()` がPDB全体を読みSHA-256を計算する。
初めて検査する曲では公開前にも同じ検証を行う。

| 合成曲数 | PDBサイズ | 全曲の解析準備時間 | 論理読み取り量 | 同じ解析済み曲を100回取得 |
| --- | ---: | ---: | ---: | ---: |
| 100 | 51,712 B | 0.205秒 | 13.05 MB | 0.094秒 / 6.50 MB |
| 1000 | 512,512 B | 13.656秒 | 1,052.10 MB | 0.640秒 / 52.58 MB |

初回カタログ作成の時間はこの表に含めない。計測対象は公開済みカタログの曲別解析部分。
曲数が10倍で読み取り量は約81倍になった。概ね「処理曲数 × PDBサイズ」のため、
PDBサイズも曲数に比例する条件では二次的に増える。

これは音声コールバックからのディスクアクセスではない。しかし、実USBでは音声先読みと
同じ媒体を利用し、ハッシュ計算はCPU・メモリ帯域も使う。再生中のI/O競合候補になる。
波形取得時にはさらにPDBの前後検証、ANLZ全体の前後ハッシュがあり、この表より処理が増える。
一覧の切り替えでも再キューされ、解析結果がキャッシュ済みでもPDB再読は残る。

対処案: 改変・媒体交換検出を維持したバッチ単位の検証と公開、デッキのロード要求を
先読みより優先する専用キュー、再生負荷に応じた先読みの間引きを検討する。
同サイズ・同mtime改変の検出を単に省く高速化は行わない。

関連: `src/library/rekordbox/rekordboxruntimetrackmodel.cpp:155` / `:339` / `:382`、
`rekordboxusbsession.cpp:419` / `:451` / `:476`、`rekordboxdevice.cpp:161` 以降。
保守元: [0049](../patches/0049-rekordbox-load-analysis-on-track-demand.patch)、
[0056](../patches/0056-browser-background-waveform-previews.patch)。

## 4. 曲ロード前の解析・波形取得が画面スレッドを待たせる（優先度: 中〜高）

ブラウザの `getTrack()` は `createTemporaryTrack()` を同期実行する。
ここで解析ワーカーと共通の `m_analysisMutex` を待ち、その後にPDB検証、
複数形式の波形ペイロード読み取り・検証、波形変換を行う。
通常のロード操作やタッチプレビューからこの経路に入る。

音声デコード用CachingReaderWorkerが動き始める前に、画面側がUSB処理を完了する必要がある。
バックグラウンド化済みの一覧波形と、デッキ用Trackの生成は別の経路である。
低速USBではロード操作・画面反応が止まる可能性がある。
今回、実USB上でのロード操作時間・GUI停止時間は未測定。

対処案: Track生成全体をワーカーへ移し、デッキ・USB世代を確認してからGUIへ返す。
同じANLZの複数形式の取得とフィンガープリント検証もまとめる。

関連: `src/library/rekordbox/rekordboxruntimetrackmodel.cpp:190`、
`rekordboxusbsession.cpp:626`、`src/widget/wtracktableview.cpp:934`。

## 5. USB保存は非同期でも共有mutexによって画面を止めうる（優先度: 中）

`writeList()`、`writePerformance()`、`writeRating()` は、セッションの `m_mutex` を
保持したままファイル読み書き・検証・commitまで実行する。
一方、画面は `state()`、`catalog()`、`sessionState()` を同じmutexで読む。
0056の行描画にも `sessionState()` の取得があり、保存中のワーカーを待つことになる。
自動履歴保存でもこの経路を使う。

音声処理は別の軽量 `SessionState::isActive()` を参照するため、このUSBセッションmutexで
音声コールバックが直接待つ経路は、今回追跡した通常再生経路では確認しなかった。
ただしGUI・操作応答には影響しうる。実USBでの待ち時間は未測定。

対処案: I/O用の排他と短時間の状態公開を分け、セッション世代を照合して結果を反映する。

関連: `src/library/rekordbox/rekordboxusbsession.cpp:284` / `:295` / `:311` / `:599` 付近。
保守元: [0037](../patches/0037-rx3-performance-and-usb-workflows.patch)。

## 6. 再生履歴を毎秒、履歴数×USB全曲数で検索する（優先度: 中）

ブラウザの1秒タイマーは画面が演奏表示でも `refreshSessionWork()` を実行する。
過去に再生済みの全Trackについて `infoForLocation()` を呼び、この関数が各USBの
全曲を線形探索する。履歴H件・カタログN曲では毎秒概ねO(H×N)の比較になる。
`QHash` の取得自体は共有コピーだが、その後の全曲探索は残る。

新しい履歴が増えていない時間にも同じ検索を繰り返すため、長時間のセットで増える負荷候補。
この項目はコードで確認した計算量であり、大規模実USBでのGUI停止時間は未測定。
対処案: ソースバインディングのセッションID・rekordbox IDから直接参照し、
新しく履歴に入った曲だけを処理する。

関連: `src/widget/wrx3browser.h:399`、`wrx3browsertools.h:211`、
`src/library/rekordbox/rekordboxfeature.cpp:427` 付近。

## その他の確認

- 音声ファイルの読み取り・デコードは `CachingReaderWorker`、音声側との連絡はFIFO。
  EngineBufferのロード排他は `tryLock()` で、待たずに無音を返す設計。
- 緊急再生用PCMはロード時に事前確保される。1デッキ約11.72 MiB、2デッキ約23.44 MiB。
  キャプチャは256フレームで平均0.0015 ms、p99 0.0016 ms、最大0.0197 ms。
  今回の計測では主なボトルネックではなかった。
- Release FXはOFFでも各デッキの `processAudio()` が全サンプルのゲイン平滑化を行う。
  安定してゲイン1のときの早期returnは改善候補だが、解除直後のフェード復帰を省略してはいけない。
  単体の削減効果は未測定で、上記の大きな問題より優先度は低い。
- マイクEQは固定ストレージを使用し、係数更新は32フレームごと。
  録音・配信のエンコードはSideChainワーカーに分離されている。
  録音先が詰まった場合はFIFOのオーバーランを起こしうるため、録音併用の実機試験は別途必要。
- Auto Cueの音頭探索はデコーダーを開いたワーカーで最大約1秒のループを持つ。
  音声コールバックへの直接配置ではないが、先頭無音の長い曲のロード時間や媒体I/Oを増やしうる。
- 波形描画は音声コールバックから分離されている。今回のoffscreenテストは、
  実画面の解像度・GPUドライバー・フレームレートの負荷を評価するものではない。

## テスト結果と再現用ファイル

- 既存ネイティブ選択: EngineBuffer、EngineMixer、EngineSync、LoopingControl、RX3、Rekordbox。
  初回は512件実行、469成功、40 skip、3失敗（別にdisabled 3件）。
  3失敗はスキン・QSSの環境変数未指定が原因で、両変数を指定した再実行では3件とも成功。
- 追加計測3件は成功。上の表は資材パスと信号出力を確認できた有効な計測のみを掲載している。
- FLX4 Beat FX / Smart CFX、Sound Color FX、Auto Loop、Loop Adjust、Jog Bend、SYNC、
  Shortcut Transport、Transport ControlsのJavaScript検証9本はすべて成功。
- Windowsの予防的識別子チェックを含む `test-windows-installer-contract.py` は成功。
  Windowsコンパイル自体は今回実施していない。
- 任意のスキン実体テスト `Rx3SmartFxTest.SkinBadgeTogglesWithOneTapAndSelectsPresetsInPlace`
  は初回skipだったが、資材指定後の追加試行ではsegmentation faultが発生した。
  原因未確定。アプリ本体での再現や性能問題との因果は未確認。
  デバッガーはこの実行環境のptrace制限で起動できず、スタックは未取得。

詳細ログ・追加計測コードは `build/realtime-audit/`（再生成可能、Git対象外）に保存。

- `audit.cpp` / `build-audit.py`: 既存オブジェクトに追加計測をリンクする実装。
- `source-hashes.json`: 調査した主要ソース9ファイルのSHA-256。
- `measurements-valid.log` / `measurements-valid.xml`: 有効な計測結果。
- `regression.log` / `regression.xml`: 初回のネイティブ選択テスト。
- `skin-fixed-env.log` / `skin-fixed-env.xml`: 3失敗を環境変数指定で再検証した結果。
- `skin-retry.log`: 任意のSmart CFXスキンテストがクラッシュした試行。
- `windows-contract.log`: Windows予防チェック。

追加計測の再実行:

```sh
python3 build/realtime-audit/build-audit.py
QT_QPA_PLATFORM=offscreen build/realtime-audit/audit-test \
  --gtest_filter='RealtimeAudit*' --gtest_color=no
```

`build/realtime-audit/CMakeCache.txt` は計測実行ファイルの資材パスを既存ソースへ向ける。
ネイティブビルドやソースの位置を変えた場合は、保存済みコンパイル・リンク情報と一緒に再取得する。
この追加実行ファイルはアプリの配布物には含めない。
