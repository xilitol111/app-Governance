# app-Governance

Claude Code運用ガイドラインの原本(source of truth)を管理するリポジトリ。

**このリポジトリにアプリのコードは置かない。** 各プロジェクト(GAME, kakeibo, kakeibo-liff, ...)は
従来通りそれぞれ独立したリポジトリのまま。ここが持つのはガイドライン本文だけ。

## 仕組み

- 本文は [`CLAUDE.md`](./CLAUDE.md) にある。
- 配布・同期のロジックは [`hooks/`](./hooks) にある3本のフックスクリプトが担う:
  - **`hooks/session-start.sh`**(`SessionStart`フック、セッション開始ごとに1回)
    このリポジトリの`main`から`CLAUDE.md`と`hooks/`配下の3ファイル自身を、
    `raw.githubusercontent.com`への`curl`で毎回re-fetchし`~/.claude/`へ反映したあと、
    現在のプロジェクトの`git log --oneline -10`・直近1件の
    コミットメッセージ全文・`git status --short`、さらに`docs/session-archive.md`が存在すれば
    その末尾4000バイト分を標準出力に出す。標準出力はセッション開始時に自動でコンテキストへ
    追加される仕組みを利用しており、CLAUDE.mdの内容が常に最新化されるのに加え、セッションが
    変わっても「直近何が起きたか」の手がかりがgit履歴+直近の会話アーカイブという形で、LLM呼び出し
    (=追加コスト)なしに自動的に読み込まれる。`tail`で末尾のみに絞っているのは、
    `session-archive.md`がこのプロジェクトの全セッション分を無期限に追記され続けるファイルであり、
    全文を毎回注入すると際限なくコストが増えるため(古い部分は必要な時に手動で`Read`すればよい、
    という設計)。これにより、five時間制限の通知(後述)を受けてClaudeが`create_session`で自ら
    作った後継セッションも、この末尾抜粋だけで「直前まで何をしていたか」を把握した状態で始まる。
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
  # provisioning, outbound access may not be guaranteed to be ready yet,
  # and this script runs under `set -e`-like all-or-nothing semantics with
  # no visible logs to debug from. Instead, this just writes a minimal
  # session-start.sh that does the real fetch — that script runs later,
  # once a real session's networking is live, and is itself tolerant of a
  # failed fetch. It uses plain `curl` against raw.githubusercontent.com
  # (app-Governance is public as of 2026-08-22), not `git clone` — so
  # unlike the git-based version this repo used through 2026-08-21, it
  # needs no auth of any kind and works from any environment with plain
  # outbound HTTPS.
  cat > ~/.claude/hooks/session-start.sh << 'HOOK'
  #!/bin/bash
  set -uo pipefail
  GOV_RAW="https://raw.githubusercontent.com/xilitol111/app-Governance/main"
  GOV_TMP=$(mktemp -d)
  GOV_SYNC_OK=1
  fetch() {
    curl -fsSL "$GOV_RAW/$1" -o "$GOV_TMP/$(basename "$1")" 2>>"$GOV_TMP/.err" || GOV_SYNC_OK=0
  }
  fetch "CLAUDE.md"
  fetch "hooks/session-start.sh"
  fetch "hooks/archive-turn.py"
  fetch "hooks/session-end.py"
  if [ "$GOV_SYNC_OK" = "1" ]; then
    mkdir -p ~/.claude/hooks
    cp "$GOV_TMP/CLAUDE.md" ~/.claude/CLAUDE.md
    for f in session-start.sh archive-turn.py session-end.py; do
      cp "$GOV_TMP/$f" ~/.claude/hooks/"$f"
      chmod +x ~/.claude/hooks/"$f"
    done
  fi
  rm -rf "$GOV_TMP"
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

## 外部Routine: 五時間枠アンカー(毎朝9時JST起動)

[Zennの記事](https://zenn.dev/trknhr/articles/ae45f1380f90b3)で紹介されていた「早朝に軽い作業を1つ起動しておくと、five_hour利用枠のリセット境界が早まり、日中に使える枠のリセット回数が増える(例: 2回→3回)」という節約策を自動化したもの。

- 実体は本リポジトリのコードではなく、アカウント側のRoutine(`create_trigger`で作成、trigger_id: `trig_01SKn2a7Y6on7ZDnoKzTTk6H`)。`kakeibo`環境(`env_01CH8G8RmBJwUGCWuLdsJFGj`)で毎日UTC 0:00(=JST 9:00)に新規セッションを1つ起動する。
- 起動されたセッションへの指示は「ツール呼び出しは一切せず、短い確認だけ返して終了する」ことに限定してあり、five_hour起点を早めるための最初のAPI呼び出しを発生させる以外の目的はない(コストを最小化するため)。
- 通知(push/email)は静音設定。管理・削除は `list_triggers` / `delete_trigger` / `update_trigger` から行う。
- 効果測定は未実施。実測データが取れたら`NOTES-2026-08-21-handoff.md`に追記する想定。

## 別マシン/別環境で使う場合

この仕組みは`kakeibo`環境専用。ローカルPCや別のClaude Code環境でも同じ内容を効かせたい場合は、
それぞれの環境で同じSetup Script(またはそれに相当する初期化手順)を個別に設定する必要がある。

**過去の既知問題(2026-08-22 解決済み)。** 当時この配布は`git clone`ベースで、
`xilitol111/game`用の別環境で検証したところ、Setup Script自体は正しく登録されていた
(`session-start.sh`は実体あり、settings.jsonのフック登録も正常)にもかかわらず、その環境の
GitHubアクセスが`xilitol111/game`のみにスコープされておりapp-Governanceが対象外だったため、
`git clone`が`fatal: could not read Username`で毎セッション無音のまま失敗し続けていた
(`2>/dev/null`で握りつぶされていたため気づけなかった)。**対応として同日、本リポジトリを
publicにしたうえで配布方式を`git clone`から`curl`(`raw.githubusercontent.com`への直接取得)
に切り替えた。** これにより環境ごとのgitアクセススコープに一切依存しなくなり、Setup Scriptさえ
登録すれば(=リポジトリアクセス権限の個別付与なしに)どの環境でも配布が効くようになった。
失敗時に`## Governance sync: FAILED`とエラー内容をセッション開始時の出力に必ず表示する仕組み
(`session-start.sh`)は、今後別の理由(GitHub全体の障害など、稀にしか起きないはずの事象)で
失敗した場合の可視化として引き続き残している。
