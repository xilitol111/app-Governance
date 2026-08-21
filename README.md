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
    あわせて、`cache_read_input_tokens`の累積を`docs/five-hour-samples.jsonl`に記録する
    (five時間利用制限の監視用ログ)。累積が`THRESHOLD_TOKENS`(現在500万)の倍数を超えるたびに
    ——1セッションにつき1回だけではなく、間隔ごとに繰り返し——Claudeに通知する(強制停止はしない)。
    通知を受けたClaudeは、単に「切り替えましょうか」と聞くのではなく、`create_session`ツールで
    実際に後継セッションを自分で作成し、ユーザーにリンクを渡す。継続性は`docs/session-archive.md`・
    git履歴・`CLAUDE.md`の自動同期で既にカバーされているため後継セッションは経緯を把握した状態で
    始まり、この自動化によってセッション切り替えの手間がほぼゼロになった分、通知の頻度を
    1500万→500万・1回限り→間隔ごとの繰り返しに引き上げた(2026-08-21)。閾値自体は
    実際にアプリの利用率表示(62%)とこのセッション自身のcache read累積を突き合わせて算出した
    ものだが、まだ1点のデータに基づく暫定値であり、今後の校正機会で精度を上げていく想定。
    経緯は`NOTES-2026-08-21-handoff.md`を参照。
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
  set -u
  mkdir -p ~/.claude/hooks

  # This script does no network I/O on purpose — it only writes local files.
  # An earlier version ran `git clone` directly here and failed
  # ("Setup script failed", non-recoverable): this early in container
  # provisioning, the environment's git-auth proxy injection isn't
  # guaranteed to be ready yet, and this script runs under `set -e`-like
  # all-or-nothing semantics with no visible logs to debug from. Instead,
  # this just writes a minimal session-start.sh that does the real fetch —
  # that script runs later, once a real session's git auth is live (verified
  # working every session so far), and is itself tolerant of a failed fetch.
  cat > ~/.claude/hooks/session-start.sh << 'HOOK'
  #!/bin/bash
  set -uo pipefail
  GOV_REPO="https://github.com/xilitol111/app-Governance"
  GOV_CLONE="$HOME/.claude/governance-src"
  if [ -d "$GOV_CLONE/.git" ]; then
    git -C "$GOV_CLONE" fetch --quiet origin main 2>/dev/null \
      && git -C "$GOV_CLONE" reset --quiet --hard origin/main 2>/dev/null
  else
    rm -rf "$GOV_CLONE"
    git clone --quiet --depth 1 --branch main "$GOV_REPO" "$GOV_CLONE" 2>/dev/null
  fi
  if [ -d "$GOV_CLONE" ] && [ -f "$GOV_CLONE/CLAUDE.md" ]; then
    mkdir -p ~/.claude/hooks
    cp "$GOV_CLONE/CLAUDE.md" ~/.claude/CLAUDE.md
    for f in session-start.sh archive-turn.py session-end.py; do
      if [ -f "$GOV_CLONE/hooks/$f" ]; then
        cp "$GOV_CLONE/hooks/$f" ~/.claude/hooks/"$f"
        chmod +x ~/.claude/hooks/"$f"
      fi
    done
  fi
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "## Recent commits"
    git log --oneline -10 2>/dev/null
    echo
    echo "## Latest commit (full message)"
    git log -1 2>/dev/null
    echo
    echo "## Uncommitted changes"
    git status --short 2>/dev/null
  fi
  HOOK
  chmod +x ~/.claude/hooks/session-start.sh

  # Empty placeholders so the hooks registered below never error on a
  # missing file, even before the first real SessionStart has populated them.
  touch ~/.claude/hooks/archive-turn.py ~/.claude/hooks/session-end.py
  chmod +x ~/.claude/hooks/archive-turn.py ~/.claude/hooks/session-end.py

  python3 - << 'PY' || true
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

  exit 0
  ```

  (既存の`~/.claude/settings.json`があってもマージするだけで上書きしない。このスクリプト自体はネットワーク通信をしないため、環境provisioning初期のタイミング問題で失敗することがない。)

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
