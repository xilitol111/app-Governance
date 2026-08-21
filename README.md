# app-Governance

Claude Code運用ガイドラインの原本(source of truth)を管理するリポジトリ。

**このリポジトリにアプリのコードは置かない。** 各プロジェクト(GAME, kakeibo, kakeibo-liff, ...)は
従来通りそれぞれ独立したリポジトリのまま。ここが持つのはガイドライン本文だけ。

## 仕組み

- 本文は [`CLAUDE.md`](./CLAUDE.md) にある。
- `kakeibo`環境(`env_01CH8G8RmBJwUGCWuLdsJFGj`)のSetup Scriptが、セッション起動時にこのファイルを
  `~/.claude/CLAUDE.md`へコピーする。これによりこの環境で開くセッションは、既存プロジェクトか新規
  プロジェクトかを問わず、常にこの内容が自動的に読み込まれる。
- Setup Scriptの内容は下記の通り。claude.aiの環境設定画面(環境名の右のセレクタ→設定ボタン)から
  `kakeibo`環境に登録する:

  ```bash
  #!/bin/bash
  set -euo pipefail
  mkdir -p ~/.claude
  curl -fsSL https://raw.githubusercontent.com/xilitol111/app-Governance/main/CLAUDE.md \
    -o ~/.claude/CLAUDE.md
  ```

## 更新方法

1. この`CLAUDE.md`を編集してコミット・`main`にマージする
2. claude.aiの`kakeibo`環境設定画面でSetup Scriptを開き、保存し直す(内容は変えなくてよい —
   保存操作自体が次回セッションでの再実行のトリガーになる)

Setup Scriptは初回セッションで一度だけ実行され、その後はコンテナの状態がキャッシュされて
自動では再実行されない。**更新後にステップ2を忘れると、新しいセッションにも古い内容が
残り続ける。**

## 別マシン/別環境で使う場合

この仕組みは`kakeibo`環境専用。ローカルPCや別のClaude Code環境でも同じ内容を効かせたい場合は、
それぞれの環境で同じSetup Script(またはそれに相当する初期化手順)を個別に設定する必要がある。
