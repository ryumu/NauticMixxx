# Raspberry Pi 5 / Linux コード調査

調査日: 2026-10-14。調査時点の対象: Mixxx 2.5.6とNauticMixxxの44パッチ。
想定実機: Raspberry Pi 5、10インチ1920×1200タッチパネル。

## 実装の進捗（0045追加後）

以下の本文は調査時点の記録です。最新の対処状況は次のとおりです。

| 項目 | 状況 |
| --- | --- |
| 1. 固定マウント先の検出 | 実マウントルートの探索を0045で追加。実機確認は未実施 |
| 2. USB交換の識別 | マウントID・diskseqを追加。同じパスでの識別変更でもセッションを無効化 |
| 3. 保存中のGUI待ち | 未対応 |
| 4. 履歴の全曲検索 | 未対応 |
| 5. Linuxテストの指定不足 | `Rekordbox*` / `TrackCapabilityPolicyTest.*` に拡張。PCで対象347件、309件成功・38件skip・失敗0 |

[0045パッチ](../patches/0045-linux-usb-mount-discovery-and-identity.patch) に、
固定マウント・重複・シンボリックリンク・交換判定・旧カーネルのfdinfo経路・
ディスク世代情報・FD解放を確認する10件のC++テストを追加しました。
この10件はホストx86_64 / Qt 6.12でASan・UBSan・LSanを有効にして通過しました。
公式ソースへの45パッチの順次適用と、生成された変更ファイルの一致も確認しました。
Linuxの指定はRekordbox関連165件のテスト定義すべてに一致します（全件の実行結果ではありません）。
2026-10-15に開発PCの依存導入後のビルド停止を再現し、0045に次の修正を追加しました。

- `wrx3trackinfo.h`: `QT_USE_QSTRINGBUILDER` 有効時に条件式の分岐が異なる型になる問題を修正。
  表示文字列を `QString` に代入してから設定します。
- `wwaveformviewer.cpp`: PCH無効時に不足する `control/controlobject.h` を直接includeします。
- `rx3beatfx_test.cpp` / `rx3display_test.cpp`: `Q_OBJECT` を持たない独自ウィジェットを
  Qtの基底型で検索し、`dynamic_cast` で型を確認します。Qt 6.12の静的検査に対応します。
- デッキ表示テスト: 文字の最下行・最上行を除いて空白行を数えます。
  座標差を使って1行多く数えていた判定を修正しました。

Linuxのブランド生成処理も、内容が変わらないファイルの更新を省略するように修正しました。
同じヘッダー・リソースの書き直しによる不要な再コンパイルを防ぎます。

CachyOS x86_64 / GCC 16.2 / Qt 6.12の `RelWithDebInfo`、PCH無効の設定で
通常のLinuxビルドスクリプトが最後まで成功しました。
本体・テスト実行ファイルをビルドし、対象347件中309件成功、38件skip、失敗0でした。
skipは外部の実USBサンプルや任意の画像出力設定が必要なテストです。
更新チェックのローカルHTTPテストは、localhostの待受けを許可した環境で実行しました。
起動用フォルダの生成、64bit ELF・プロファイル・デスクトップ登録の検証と
ランチャーによる `--version` の実行も成功しました。
GUIを使った描画・音声・タッチの確認、およびPi上での全体ビルド・安全な取り外し・
物理USB交換の検証はまだ必要です。

新しいカーネルでは再利用されないマウントIDを使用します。
古いカーネルではブロックデバイスのdiskseqが必要で、識別情報を読み取れない媒体は拒否します。
非ブロックの仮想ファイルシステムでは旧マウントIDのみになる場合があり、
古いカーネル上の特殊なFUSE/仮想マウントは実機で追加確認が必要です。

## 結論

ARM64向けのビルド経路とLinux向けの起動・パッケージ処理は存在します。
ソースアーカイブのSHA-256検証と44パッチの適用は成功しました。
Debian Bookworm/TrixieのARM64索引上で、既存依存導入スクリプトのパッケージは
別名・移行パッケージを含めすべて解決先がありました。
今回、コンパイル不能と断定できる問題は確認していません。
全体のネイティブビルド、Pi上の描画・タッチ・音声は未検証です。

優先して対応したい点は、LinuxのUSB探索範囲、USB識別の弱さ、書き戻し中のGUI待ち、
毎秒の全曲検索、Linuxテストの不足です。

## 1. 特定のマウント先にあるUSBを発見できない（P2、コードで確認）

対象: [0010パッチのLinux探索](../patches/0010-rekordbox-usb-only-runtime.patch)、
[0013パッチの手動認証](../patches/0013-rx3-usb-autodiscovery.patch)。
適用後の `src/library/rekordbox/rekordboxfeature.cpp` の
`findRekordboxDevices()` / `startDiscovery()` / `authorizeVolume()`。

Linuxの探索先は `/media`、`/media/$USER`、`/run/media/$USER` の直下です。
`QStorageInfo::mountedVolumes()` はマウント変化の監視に使われますが、
そのルート一覧をUSB探索の候補として渡していません。
また、保存された手動認証先を読み出す処理と、フォルダ選択による認証はmacOS専用です。
Linuxの `authorizeVolume()` は何も行いません。

したがって、例えば `/mnt/djusb/PIONEER/rekordbox/export.pdb` が存在するUSBを
`/mnt/djusb` にマウントしてもSOURCEには追加されません。
通常のデスクトップ自動マウント先は探索範囲に入りますが、Piの専用機化やfstabによる
固定マウントで問題になります。

改善案: Linuxの実マウントルートを探索候補に追加するか、Linuxにも明示的なフォルダ登録を実装する。
現在の [Linuxガイド](LINUX-RASPBERRY-PI.md) の「特殊なマウント先は手動認証で対応」という
記載は、Linuxの実装と一致していません。

## 2. LinuxのUSB識別にデバイス名の再利用を区別する情報がない（P2、条件付きリスク）

対象: [0037パッチ](../patches/0037-rx3-performance-and-usb-workflows.patch) の
`src/util/rx3usbstorage.h` / `DeviceSnapshot::matches()` と、
[0013パッチ](../patches/0013-rx3-usb-autodiscovery.patch) の2秒周期のマウント監視。

macOSでは識別値にファイルシステムのfsidを追加していますが、Linuxでは
`QStorageInfo::device()` の値だけです。
[Qtの公式説明](https://doc.qt.io/qt-6/qstorageinfo.html#device) によると、Unixでは通常
`/dev/sda1` のようなデバイスパスが返ります。これは媒体固有の識別子ではありません。

マウントの消失を監視が捉えなかった場合に、別のUSBが同じマウント先・デバイスパスに入り、
`export.pdb` も同じ内容なら、既存セッションの同一性検査を通過する構造です。
既存の保存ガードもこの識別値を使うため、別媒体への書き戻しを拒否できない可能性があります。

実際の `rekordboxdevice.cpp` をホストのQt6Coreとコンパイルした小さな検証プログラムで、
同じルート・デバイス名・PDBハッシュを持つ値は一致し、デバイス名だけを変えた値は不一致になる
ことを確認しました。実USB交換による再現は行っていません。

改善案: LinuxではマウントID・udevによる媒体情報などを組み合わせ、着脱イベントで世代を更新する。
UUIDだけでは複製媒体を区別できない場合もあるため、セッション世代の管理と併用する。

## 3. USBへの保存中にGUIが同じmutexを待つ（P2、コードで確認）

対象: [0037パッチ](../patches/0037-rx3-performance-and-usb-workflows.patch) の
`RekordboxUsbSession::writeList()` / `writePerformance()`、
`src/widget/wrx3browsertools.h` の `refreshSessionWork()`。
読み取り側の `state()` / `catalog()` は [0010パッチ](../patches/0010-rekordbox-usb-only-runtime.patch)。

保存処理はワーカースレッドで実行されますが、`m_mutex` を保持したまま、PDB/ANLZの読み取り、
ハッシュ計算、バックアップ、ファイル書き込みを行います。
GUI側の `catalogForRoot()` / `infoForLocation()` は同じmutexを取る `state()` / `catalog()` を呼びます。
これらは毎秒の履歴処理や表示更新でも使用されます。

保存に時間がかかるUSBでは、GUIスレッドが保存終了まで待ち、タッチ操作や表示更新が止まる
可能性があります。Linux専用の問題ではありませんが、Piと低速USBの組み合わせで影響が増します。
この経路だけで音声スレッドの停止を断定することはできません。

改善案: 検証対象を短いロックで取得し、重いI/Oはロック外で実行する。
公開時にセッションの世代と変更状態を再確認する設計が必要です。

## 4. 毎秒、再生履歴の全曲についてカタログ全体を検索する（P2、性能上の構造的リスク）

対象: [0037パッチ](../patches/0037-rx3-performance-and-usb-workflows.patch) の
`WRx3Browser::refreshSessionWork()` と `RekordboxFeature::infoForLocation()`。

GUIの1秒タイマーで、これまで再生した各トラックを処理します。
その都度 `infoForLocation()` が各USBの `catalog->tracks()` を先頭から検索します。
再生履歴は `m_playedTracks` に追加され、件数の上限や差分処理はこの経路にありません。
履歴の保存件数が増えていなくても検索は先に実行されます。

曲数をN、再生履歴数をHとすると、最悪では毎秒O(N×H)の比較になります。
例えばカタログ1万曲・履歴200曲では、1秒ごとに最大約200万件のパス比較が必要です。
これは比較回数の目安であり、Piでの処理時間は未計測です。

改善案: パスからトラックへの索引を作る、source bindingの曲IDを使う、
新しく再生済みになった曲だけを履歴に追加する。

## 5. LinuxビルドでUSB関連テスト129件が選択されない（P2、検証不足）

対象: [Linuxビルドスクリプト](../scripts/build-mixxx-rx3-linux.sh) の `--gtest_filter`。
UbuntuとDebian ARM64のワークフローはどちらもこのスクリプトを使用します。

適用後の `src/test/rekordbox*test.cpp` にあるTEST定義をフィルタと照合すると、
Rekordbox関連155件のうち26件が選択対象で、129件が対象外でした。
この件数は定義とフィルタの静的な集計であり、実行結果ではありません。

除外される例:

- `RekordboxUsbSessionTest`: 32件。マウント識別、変更拒否、USBへの保存など。
- `RekordboxDeviceTest`: 8件。パス閉じ込め、マウント/カタログ変更検出など。
- `RekordboxLazyWaveformTest`: 10件。遅延読み込みとキャッシュの整合性など。
- `RekordboxDatabaseTest` / `RekordboxPlaylistTest`: 合計19件。

別途 `TrackCapabilityPolicyTest.*` などもLinuxの指定に含まれていません。
改善案: 対象を `Rekordbox*` と関連ポリシーのスイートへ広げ、必要な外部fixtureがない
テストのskipは結果に明記する。

## 実機で確認が必要な点

- **描画負荷:** 共通プロファイルは `FrameRate 60`、`VSync 0`、shaderベースの波形です。
  1920×1200で2デッキ・エフェクトを動かした時のGPU/CPU使用率、フレーム時間、音切れを測定する。
  現状の [GUI smoke test](../scripts/smoke-linux-gui.py) はXvfbとソフトウェアMesaを強制し、
  PiのV3DやWaylandを検証していません。
- **タッチ:** ブラウザはQScroller、X-PADはネイティブtouch eventに対応しています。
  その他の多くの操作はmouse eventを使います。タップだけでなく長押し・ドラッグ・キャンセル・
  複数の指による同時操作を確認する。全操作のマルチタッチ対応は確認できていません。
- **Wayland:** Pi用の新しいセットアップは `qt6-wayland` を導入しますが、共通の
  `install-linux-build-deps.sh` は導入しません。直接共通スクリプトを使う最小構成では
  Waylandプラグイン/XWaylandの有無を確認する。
- **音声:** LinuxではCoreAudio固有のMP3補正は適用されません。
  WAV/MP3のキュー・ループ位置、キー ロック、録音、マスター/ヘッドホン出力を検証する。
  RubberBandのFiner設定も共通プロファイルに含まれ、キー ロック使用時の負荷を測る必要があります。
- **表示倍率:** 1280×800はスキンの基準値です。適用後の `WReferenceScaler` は
  viewportの最小を基準の半分にし、ウィジェットを縮小できます。
  そのため1280×800をアプリ全体の絶対的な最小値とみなすことはできません。
  今回の1920×1200では、全画面と100/125/150%で実際の論理サイズ・文字・タッチ領域を確認する。
- **更新:** Linuxの `createIntegratedUpdater()` はnullptrを返し、手動ダウンロードへ進みます。
  macOS/Windowsと同じ自動インストール機能は実装されていません。

## 実施した確認と限界

- 公式Mixxx 2.5.6アーカイブのSHA-256検証、44パッチの順次適用: 成功。
- Debian Bookworm/Trixie mainのARM64 Packages索引と、導入スクリプトの要求名・Providesを照合:
  解決先なしの要求名は0件。Qtの旧名称はProvides、TagLibの旧名称は移行パッケージで対応。
- 実際の `rekordboxdevice.cpp` を使った識別比較の検証: ホストx86_64 / Qt 6.12で実行。
- Pi開発チェックの5テスト、Linuxパッケージ/プロファイル検証: 成功。
- USB-only静的チェック: 復元ソースを指定して10/10成功。
  このチェックの既定ソースパスは従来のmacOSビルドルートで、Linuxのビルドルートは自動検出しません。
- Windows識別子/インストーラ契約チェック: 成功。

ソースと調査用の索引・検証結果はローカルの `build/pi-linux-audit/` に置き、Gitの対象外です。
実装コードの修正、OSパッケージのインストール、全体のコンパイル、Pi上の動作確認は今回行っていません。
