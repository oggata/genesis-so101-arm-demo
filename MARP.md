# Marp → GitHub Pages 公開手順メモ

---

## 全体の流れ

```
MDファイルを書く
    ↓
Marpでローカル確認（VS Code）
    ↓
GitHubにpush
    ↓
GitHub Actionsが自動でHTMLに変換
    ↓
GitHub Pagesで公開 🎉
```

---

## Step 1 — Marpをインストールする

### VS Code拡張（プレビュー用・まずはこれだけでOK）

1. VS Codeを開く
2. 拡張機能タブ（Cmd+Shift+X）で `Marp for VS Code` を検索
3. インストール
4. MDファイルを開くと右上にプレビューボタンが現れる

### CLIもインストールしておく（HTML出力用）

```bash
npm install -g @marp-team/marp-cli

# 動作確認
marp --version
```

---

## Step 2 — ローカルでHTMLに変換する

```bash
# HTMLに変換（自己完結型・1ファイルで完結）
marp genesis_slides_marp.md -o docs/slides.html

# PDFに変換したい場合
marp genesis_slides_marp.md --pdf -o slides.pdf

# PPTXに変換したい場合
marp genesis_slides_marp.md --pptx -o slides.pptx

# ローカルでライブプレビューしながら編集
marp --server .
# → http://localhost:8080 でブラウザ確認できる
```

> ⚠️ `docs/` フォルダは事前に作っておくこと（`mkdir docs`）

---

## Step 3 — GitHubリポジトリを準備する

### フォルダ構成

```
リポジトリ/
├── .github/
│   └── workflows/
│       └── marp.yml        ← GitHub Actions設定
├── docs/
│   └── slides.html         ← 自動生成される（最初は空でOK）
├── genesis_slides_marp.md  ← このファイルを編集していく
└── README.md
```

### 手順

```bash
# docs フォルダだけ先に作る
mkdir docs
touch docs/.gitkeep   # 空フォルダはgitに追跡されないため

git add .
git commit -m "init"
git push
```

---

## Step 4 — GitHub Actionsを設定する

`.github/workflows/marp.yml` を以下の内容で作成：

```yaml
name: Deploy Marp Slides to GitHub Pages

on:
  push:
    branches:
      - main          # mainブランチにpushしたら自動実行

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write   # gh-pagesブランチへの書き込み権限

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Convert Marp to HTML
        uses: docker://marpteam/marp-cli:latest
        with:
          args: genesis_slides_marp.md -o docs/slides.html --html
        env:
          MARP_USER: root

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs
```

```bash
git add .github/workflows/marp.yml
git commit -m "add: GitHub Actions for Marp"
git push
```

---

## Step 5 — GitHub PagesをONにする

1. GitHubのリポジトリページを開く
2. **Settings** タブをクリック
3. 左メニューの **Pages** をクリック
4. Source を `Deploy from a branch` に設定
5. Branch を `gh-pages` / `/ (root)` に設定
6. **Save** をクリック

> GitHub Actionsが初回pushで `gh-pages` ブランチを自動作成するので、
> Actionsが完走してからPagesの設定をするとスムーズ。

---

## 公開後のURL

```
https://ユーザー名.github.io/リポジトリ名/slides.html
```

### 例（genesis-so101-arm-demoの場合）

```
https://oggata.github.io/genesis-so101-arm-demo/slides.html
```

---

## 日常の更新フロー（設定完了後）

```bash
# 1. MDファイルを編集する
code genesis_slides_marp.md

# 2. pushするだけ（あとはActionsが自動でやってくれる）
git add genesis_slides_marp.md
git commit -m "update: スライド内容を更新"
git push

# 3. 数分後にURLを開くと更新されている 🎉
```

---

## トラブルシューティング

### Actionsが失敗する場合

- リポジトリの **Settings → Actions → General** で
  `Read and write permissions` にチェックが入っているか確認

### スライドのスタイルが崩れる場合

- `--html` フラグを忘れずに（インラインHTMLを有効化）
- フォントはシステムフォントに依存するため、
  Webフォントを使う場合はCSSに `@import` を追加

### ローカルでPDF出力に失敗する場合

```bash
# Puppeteerが必要な場合
marp --pdf --allow-local-files genesis_slides_marp.md -o slides.pdf
```

---

## まとめ

| やること | コマンド / 操作 |
|----------|----------------|
| ローカルプレビュー | VS Code + Marp拡張 |
| HTML変換 | `marp ファイル名.md -o docs/slides.html` |
| 自動デプロイ | `.github/workflows/marp.yml` を設置してpush |
| Pages有効化 | Settings → Pages → `gh-pages` ブランチを選択 |
| 更新 | MDを編集してpushするだけ |