# Raspberry Pi 5 開発環境

NauticMixxxをRaspberry Pi 5と10インチタッチパネルで動かすための準備手順です。
まずPi上でネイティブビルドし、画面・音声・USBの動作を実機で確認します。
PCではソース編集やGit管理を行い、SSHでPiのビルドを操作できます。
この手順の追加時点では、Pi 5でのコンパイルと実機動作は未検証です。

## 1. 既存OSを確認する

Piのターミナルで実行してください。OSを入れ直す前に、現在の構成を確認します。

```sh
cat /etc/os-release
cat /proc/device-tree/model
uname -m
getconf LONG_BIT
dpkg --print-architecture
free -h
df -h .
```

このセットアップの対象は **Raspberry Pi OS / Debian 12 Bookworm・13 Trixieの
64bit版、Raspberry Pi 5** です。カーネルは `aarch64`、ユーザーランドは `64` / `arm64`
が必要です。Ubuntu向けには既存の [Linux手順](LINUX-RASPBERRY-PI.md) を使用します。
画面のテストにはデスクトップ環境が必要です。Lite版ではデスクトップ環境も別途準備します。

ビルドの空き容量は15 GiB以上を計画上の目安にし、まずコンパイラ並列数は1にします。
実際の所要時間・RAM使用量は未計測です。PiのRAM容量・冷却・電源を確認してから
並列数を増やします。

## 2. SSHを有効にする

Raspberry Pi OSのPi本体で実行します。

```sh
sudo raspi-config
```

`Interface Options` → `SSH` → 有効化を選び、終了します。
メニュー名はOS版によって多少異なります。IPアドレスとユーザー名を確認します。

```sh
hostname -I
whoami
```

PCを同じネットワークに接続し、次を実行します。
`YOUR_USER` / `PI_IP_ADDRESS` は上で確認した値に置き換えます。

```sh
ssh YOUR_USER@PI_IP_ADDRESS
```

パスワードはSSHの入力欄で入力します。鍵認証を使う場合は、PCにある公開鍵を
`ssh-copy-id -i 公開鍵のパス YOUR_USER@PI_IP_ADDRESS` で追加できます。
詳しくは [Raspberry Pi公式のSSH手順](https://www.raspberrypi.com/documentation/computers/remote-access.html#access-a-remote-terminal-with-ssh)
を参照してください。

## 3. ソースを用意する

Pi上で、今回のスクリプトを含む作業ツリーを用意します。
ローカル変更がまだリモートへ反映されていない場合は、PCのこのプロジェクトのルートで
以下を実行してコピーできます。既存ファイルの削除は行いません。

```sh
ssh YOUR_USER@PI_IP_ADDRESS 'mkdir -p ~/projects/NauticMixxx'
rsync -av --exclude='.git/' --exclude='build/' --exclude='tmp/' \
  --exclude='release/' --exclude='node_modules/' --exclude='__pycache__/' \
  --exclude='.env' --exclude='.env.*' --exclude='.aws/' --exclude='.codex/' \
  --exclude='.agents/' --exclude='*.log' \
  ./ YOUR_USER@PI_IP_ADDRESS:projects/NauticMixxx/
```

PCにも `rsync` が必要です。Git管理する場合は、変更が入ったブランチをPiでclone/check outする
方法でも構いません。ビルドはPiの通常ユーザーで行います。

## 4. 開発ツールをインストールする

以下はPiで実行します。

```sh
cd ~/projects/NauticMixxx
./scripts/setup-raspberry-pi-dev.sh
```

最初にPi 5・OS・64bitユーザーランドを確認し、対象外ならパッケージ導入前に終了します。
既存のLinux依存導入スクリプトでGCC、CMake、Ninja、Qt 6、音声/コーデック開発パッケージを
導入した後、GDB、Node.js、rsync、tmux、Mesa/ALSA/libinput診断ツールとQt Waylandプラグインを
追加します。`sudo apt-get`でOSのパッケージを追加し、ビルドやアプリは通常ユーザーで動かします。

再チェックだけなら次を実行します。ファイルやOS設定は変更しません。

```sh
python3 scripts/check-raspberry-pi-dev.py
```

ツール確認が成功しても、全依存ライブラリの解決は次のCMake構成時に確認します。
SSH内でデスクトップが検出されない旨の表示は、ビルドの失敗条件ではありません。

## 5. ビルド・テストする

SSH切断後もビルドを続けたい場合は、先に `tmux new -s nautic-build` を実行します。

```sh
RX3_BUILD_JOBS=1 RX3_BUILD_TYPE=RelWithDebInfo ./scripts/build-mixxx-rx3-linux.sh
```

公式Mixxx 2.5.6ソースのSHA-256を検証し、NauticMixxxのパッチをすべて適用して
ARM64バイナリを生成します。ネイティブのRX3テストも実行します。
`RelWithDebInfo`は最適化とデバッグ情報を有効にします。省メモリ設定は既存のLinux経路を使います。
通常の配布用ビルドの既定値は引き続き `Release` です。

```sh
python3 scripts/test-windows-installer-contract.py
python3 scripts/test-raspberry-pi-dev.py
python3 scripts/test-linux-package.py --stage "build/test-candidate/$(cat VERSION)-linux-aarch64/stage"
```

ソースの編集対象は、生成された
`build/test-candidate/<VERSION>-linux-aarch64/mixxx-2.5.6/` 内です。
エディタ用の `compile_commands.json` は同じビルドルートの `native/` に生成されます。
このリポジトリのルートを `cmake -S .` でビルドすることはできません。
共有C++コードにはWindowsでマクロになる `near` / `far` を識別子として使わないでください。

生成ソースへの変更は、対応する `patches/` のパッチへ反映して管理します。
パッチ内容を変えた場合は、新しい `RX3_BUILD_ROOT` を指定します。
既存ビルド内の手編集は、自動的にリポジトリへ取り込まれません。

## 5.1. Pi向け最適化ビルドを選ぶ場合

Pi 4・5共通版とPi 5専用版は、通常のLinuxビルドとは別のスクリプトで選べます。
依存パッケージは同じです。Pi 5上では、どちらもビルド・実行できます。

```sh
# Pi 4・5共通：Cortex-A72向け
./scripts/build-mixxx-rx3-pi4.sh

# Pi 5専用：Cortex-A76向け。Pi 4では使わないでください。
./scripts/build-mixxx-rx3-pi5.sh
```

標準の出力先は、それぞれ `build/test-candidate/<VERSION>-linux-aarch64-pi4/` と
`build/test-candidate/<VERSION>-linux-aarch64-pi5/` です。通常版とビルドを分離し、
成功したビルドを既存のデスクトップランチャーへ登録します。実行するファイルは
各出力先の `stage/bin/nauticmixxx` です。`RX3_BUILD_ROOT` で出力先を変える場合も、
CPU対象ごとに別のルートを指定します。パッチ変更後は新しいルートを使用します。

両方のPi向けビルドでは、RX3の全曲波形を表示解像度の画像として保持し、同じ波形の
再計算を減らします。曲・波形の色モード・EQ・サイズ・表示倍率が変わると再生成します。
再生位置やキュー、終端警告は従来どおり更新します。画像は1ウィジェットあたり最大
16 MiBで、大きすぎる場合や確保できない場合は従来の直接描画へ戻ります。
画質・フレームレート・音声設定・保存済みの好みは変更しません。
通常のLinux版・Windows版・macOS版は従来の描画経路を使います。

LTOは初期状態では無効です。ビルド時のメモリ使用量が増えるので、比較するときだけ
`RX3_PI_LTO=ON ./scripts/build-mixxx-rx3-pi5.sh` のように指定します。
CPU対象とLTO設定は `stage/rx3-build.json` に記録します。
高速化の程度や音切れへの影響は、2デッキ再生中の実機計測で確認する必要があります。

## 6. 10インチ画面で起動する

Piのデスクトップ上のターミナルで実行します。

```sh
"./build/test-candidate/$(cat VERSION)-linux-aarch64/stage/bin/nauticmixxx"
```

今回のパネルは **10インチ・1920×1200** です。
スキンXMLの `MinimumSize` / `ReferenceSize` は **1280×800** で、
パネルと同じ16:10です。適用後の `WReferenceScaler` はviewportの最小を640×400にし、
ウィジェットを縮小できるため、1280×800はアプリ全体の絶対的な最小値ではありません。
今回の解像度と縦横比は基準レイアウトに適合します。
表示倍率によるデスクトップ全体の論理サイズは次のとおりです。

| 表示倍率 | 論理サイズ | 実機での確認方針 |
| --- | --- | --- |
| 100% | 1920×1200 | 表示の基準確認。10インチでは操作部が小さく感じられる可能性あり |
| 125% | 1536×960 | 最初に試す倍率。操作部の大きさとウィンドウの余白を確認 |
| 150% | 1280×800 | スキンの基準サイズと一致。全画面で確認 |

この換算はアプリに同じ倍率が適用される場合の値です。
デスクトップのパネルやウィンドウ枠は利用可能な領域を減らします。
OS・Qt・X11/Waylandの組み合わせで実際の拡大挙動を確認し、
OSの倍率と `QT_SCALE_FACTOR` を重ねて指定しないようにします。
表示が収まることに加え、タッチで各操作部を押せるかを実機で確認します。
HDMI＋USBタッチとDSIでは設定方法が異なるため、型番確認後に表示・回転・入力座標を調整します。

```sh
glxinfo -B
aplay -l
sudo libinput list-devices
```

`glxinfo`はX11/XWayland経由の参考情報です。Waylandでのアプリ自身の描画確認も必要です。
`llvmpipe` / `softpipe` はソフトウェア描画です。
[MesaのV3Dドライバ](https://docs.mesa3d.org/drivers/v3d.html) はPi 5に対応していますが、
それだけでNauticMixxxの性能を保証するものではありません。
タッチはOSで認識されることと、アプリの各操作が使えることを分けて確認します。
音声はマスター/ヘッドホン出力、2デッキ再生、ドロップアウトを実機で確認します。

## クロスコンパイルへ移行する場合

PC上でARM64をビルドすることは可能ですが、既存Linuxスクリプトはネイティブ専用です。
今回のセットアップではクロスコンパイル環境を作りません。
まずPiのOS版・ARM64・Qt版を確定し、次を揃える必要があります。

- ARM64用GCCとCMake toolchain file。
- Piと一致するOS/Qt/音声ライブラリのヘッダと共有ライブラリ（sysroot）。
- PC上で実行できるQtの `moc` / `rcc` 等と必要なコード生成ツール。
- ARM64バイナリをPiでテスト・配置する経路。

Qtはホストとターゲットのバージョンを揃えることを推奨しています。
詳細は [Qt公式のクロスコンパイル説明](https://doc.qt.io/qt-6/cross-compiling-qt.html) を参照してください。
CachyOSの最新ライブラリをそのままPi用の依存関係として使うことはできません。
ARM64コンテナをQEMUで実行する方法もありますが、これはARM64環境のエミュレーションで、
真のクロスコンパイルとは異なりビルド時間の短縮は保証できません。
