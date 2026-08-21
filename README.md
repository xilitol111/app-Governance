# app-Governance

Claude Code運用ガイドラインの原本(source of truth)を管理するリポジトリ。

**このリポジトリにアプリのコードは置かない。** 各プロジェクト(GAME, kakeibo, kakeibo-liff, ...)は
従来通りそれぞれ独立したリポジトリのまま。ここが持つのはガイドライン本文だけ。

## 仕組み

- 本文は [`CLAUDE.md`](./CLAUDE.md) にある。
- 配布・同期のロジックは [`hooks/`](./hooks) にある3本のフックスクリプトが担う:
  - **`hooks/session-start.sh`**(`SessionStart`フック、セッション開始ごとに1回)
    このリポジトリの`main`から`CLAUDE.md`と`hooks/`配下の3ファイル自身を毎回re-fetchし
    `~/.claude/`へ反映したあと、現在のプロジェクトの`git log --oneline -10`・直近1件の
    コミットメッセージ全文・`git status --short`を標準出力に出す。標準出力はセッション開始時に
    自動でコンテキストへ追加される仕組みを利用しており、CLAUDE.mdの内容が常に最新化されるのに加え、
    セッションが変わっても「直近何が起きたか」の手がかりが数行分だけ自動的に読み込まれる。
  - **`hooks/archive-turn.py`**(`Stop`フック、Claudeが応答を終えるたび=毎ターン)
    会話のトランスクリプトファイルを読むだけで、**LLMは一切呼ばない**。直近のClaudeの発言を
    そのプロジェクトの`docs/session-archive.md`にローカルで追記するだけなので、追加のトークン
    消費はゼロ。このファイルは後で必要な時に読みに行くための保管庫であり、セッション開始時に
    自動でコンテキストへ注入はされない(それをすると際限なくコストが積み上がるため)。
  - **`hooks/session-end.py`**(`SessionEnd`フック、セッションが終了するたび=1セッションにつき1回、
    ユーザーが明示的に閉じる必要はなく自動的に発火する)
    `docs/session-archive.md`に変更があれば、1セッション分をまとめて1コミットとしてpushする
    (毎ターンコミットすると履歴が汚れるため、頻度をここで絞っている)。git操作のみでLLM呼び出しは
    ないため、これも追加コストはゼロ。
- 上記3本は`kakeibo`環境(`env_01CH8G8RmBJwUGCWuLdsJFGj`)のSetup Scriptが最初の1回だけインストールする。
  以降は`session-start.sh`自身が毎セッション自分自身と兄弟ファイルを再取得するため、内容を更新しても
  Setup Scriptを触り直す必要はない(後述)。
- Setup Scriptの内容は下記の通り。claude.aiの環境設定画面(環境名の右のセレクタ→設定ボタン)から
  `kakeibo`環境に登録する:

  ```bash
  #!/bin/bash
  set -euo pipefail
  mkdir -p ~/.claude/hooks

  RAW_BASE="https://raw.githubusercontent.com/xilitol111/app-Governance/main"
  for f in session-start.sh archive-turn.py session-end.py; do
    curl -fsSL "$RAW_BASE/hooks/$f" -o ~/.claude/hooks/"$f"
    chmod +x ~/.claude/hooks/"$f"
  done
  curl -fsSL "$RAW_BASE/CLAUDE.md" -o ~/.claude/CLAUDE.md

  python3 - << 'PY'
  import json, os
  path = os.path.expanduser("~/.claude/settings.json")
  try:
      with open(path) as f:
          settings = json.load(f)
  except (FileNotFoundError, json.JSONDecodeError):
      settings = {}

  hooks = settings.setdefault("hooks", {})

  def add(event, command):
      entries = hooks.setdefault(event, [])
      item = {"hooks": [{"type": "command", "command": command}]}
      if item not in entries:
          entries.append(item)

  add("SessionStart", "~/.claude/hooks/session-start.sh")
  add("Stop", "~/.claude/hooks/archive-turn.py")
  add("SessionEnd", "~/.claude/hooks/session-end.py")

  with open(path, "w") as f:
      json.dump(settings, f, indent=2)
  PY
  ```

  (既存の`~/.claude/settings.json`があってもマージするだけで上書きしない。)

## 更新方法

`CLAUDE.md`やフックのロジック(`hooks/`配下)を編集して`main`にマージするだけでよい。
`session-start.sh`が毎セッション自分自身と兄弟ファイルを再取得するため、**Setup Scriptを
再度貼り付けたり保存し直したりする必要はない**。次に開かれるセッションから自動的に最新化される。

## 自動コミット・pushについて

`session-end.py`は、`docs/session-archive.md`に変更があれば**ユーザーの確認なしに自動で
コミット・pushする**。これは「セッションの会話ログを保管する」という目的専用に限定した動作で、
それ以外のファイルには一切触れない。この自動化は本リポジトリで明示的に合意した上で組み込んでいる。

## 別マシン/別環境で使う場合

この仕組みは`kakeibo`環境専用。ローカルPCや別のClaude Code環境でも同じ内容を効かせたい場合は、
それぞれの環境で同じSetup Script(またはそれに相当する初期化手順)を個別に設定する必要がある。
