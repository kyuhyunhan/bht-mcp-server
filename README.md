# bht-mcp

MCP server for the [BHt (Biblia Hebraica transcripta)](https://www.bht.gwi.uni-muenchen.de/) Hebrew Bible database at LMU Munich.

Ask your AI assistant to search, analyze, and compare 489,000+ morphologically analyzed Hebrew Bible tokens — directly from your chat interface.

```
You:  "Compare the use of root BRʾ (create) in Genesis vs Isaiah"
AI:   [calls bht_search with Wurzel filter for each book, then bht_token_detail
       on selected tokens — returns morphological breakdowns, verbal stems,
       and syntactic contexts from both books]
```

No Hebrew expertise is needed to get started. The AI reads the linguistic data and explains it to you.

[한국어](#한국어)

---

## About BHt

BHt (Biblia Hebraica transcripta) is a digital transcription of the Hebrew Bible maintained at LMU Munich under the direction of Prof. Wolfgang Richter. It features:

- **489,437 tokens** with full morphological analysis
- **Richter transcription system** — Latin-script phonemic representation (e.g., `barā(ʾ)` for בָּרָא)
- **5-class part-of-speech system** (Hauptwortart, Nebenwortart, Fügwortart, etc.)
- **Syntactic trees** at word-level (Wortfügungsebene) and sentence-level (Satzfügungsebene)
- **Textual criticism annotations** with Greek/Masoretic manuscript variant data
- **8 Sirach manuscript fragments** (Ben Sira, from Cairo Genizah and Masada)

---

## Table of Contents

- [About BHt](#about-bht)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Setting Up Your MCP Client](#setting-up-your-mcp-client)
- [Research Scenarios](#research-scenarios)
  - [Getting Started](#getting-started)
  - [Intermediate](#intermediate)
  - [Advanced](#advanced)
- [Tool Reference](#tool-reference)
- [Book Codes & Search Fields](#book-codes--search-fields)
- [Rate Limits](#rate-limits)
- [License](#license)
- [한국어](#한국어)

---

## How It Works

```
┌──────────────┐  stdio  ┌──────────────────┐  cache miss  ┌─────────────┐
│  MCP Client  │ ───────→│  bht-mcp         │ ───────────→│  BHt Website │
│  (Claude,    │ ←───────│  (local process) │ ←───────────│  (LMU Munich)│
│   Cursor,    │         │  ┌────────────┐  │              └─────────────┘
│   etc.)      │         │  │ ~/.bht/    │  │
└──────────────┘         │  │ cache.db   │  │  ← local SQLite cache
                         │  └────────────┘  │
                         └──────────────────┘
```

- **Runs entirely on your machine.** No remote server, no API keys, no cost.
- **Progressive caching.** The first search for a book fetches all its tokens in one request. After that, searches in the same book are instant — zero network calls.
- **Respectful.** Built-in rate limits (1 req/s, 150 HTML pages/day) protect the university server. The tool never bulk-scrapes.

---

## Installation

### 1. Install Python (skip if already installed)

Check first:

```bash
python3 --version
```

If you see `Python 3.11` or higher, skip to step 2.

**If Python is not installed:**

| Platform | Command |
|----------|---------|
| **macOS** | `brew install python` (requires [Homebrew](https://brew.sh/)) |
| **macOS (no Homebrew)** | Download from [python.org/downloads](https://www.python.org/downloads/) |
| **Windows** | Download from [python.org/downloads](https://www.python.org/downloads/). Check "Add Python to PATH" during install. |
| **Linux (Debian/Ubuntu)** | `sudo apt install python3 python3-pip` |

### 2. Install bht-mcp

```bash
pip install bht-mcp
```

Verify:

```bash
bht-mcp --help
```

If `pip` is not recognized, try `pip3` instead.

---

## Setting Up Your MCP Client

MCP (Model Context Protocol) lets AI assistants use external tools. You need to tell your AI client about bht-mcp. Choose your client below:

### Claude Desktop / Claude Code

Edit your MCP settings (Settings → Developer → MCP Servers) and add:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

### Cursor

Open Settings → MCP → Add Server:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

### Other MCP-compatible clients

Any client that supports MCP stdio transport can use bht-mcp. The server command is simply `bht-mcp`.

After adding, restart your client. You should see 7 BHt tools available.

---

## Research Scenarios

### Getting Started

#### Read a verse

> "Show me Genesis 1:1 word by word with grammatical analysis"

The AI calls `bht_search` to find all tokens in the verse, then `bht_token_detail` on each to get morphology:

```
barā(ʾ) — Suffixkonjugation, 3rd person masc. singular, Qal stem, root BRʾ
ʾïlō*hīm — Substantiv, masc. plural, base ʾl-h
ʾȧt — Praeposition
ha=šamaym — Substantiv with article, masc. plural
```

#### Explore a root

> "Find all forms of root ʾMR (say/speak) in the Psalms"

```
bht_search(filters=[{field:"buch", value:"Ps"}, {field:"Wurzel", value:"ʾMR"}])
```

#### Check manuscript variants

> "Are there textual variants in Genesis 1?"

```
bht_text_annotations(buch="Gen", kapitel=1)
→ Gen 1,7c — "kin": differs in Greek (G); G adds 7c text
→ Gen 1,9b — "maqōm": G reads miqwǟ, MT reads miqwē-m?
```

### Intermediate

#### Verbal stem distribution in a book

> "What verbal stems appear in Ecclesiastes, and how frequent are they?"

The AI searches for all verbs in Kohelet, groups by stem:

```
bht_search(filters=[{field:"buch", value:"Koh"}, {field:"wa", value:"11 VERB"}], limit=1000)
→ G (Qal): 312, D (Piel): 45, H (Hiphil): 67, N (Niphal): 28, ...
```

#### Compare sentence structure across books

> "Compare the syntactic structure of Gen 1:1 and John's prologue-style opening in Jes 40:1"

```
bht_sentence_analysis(buch="Gen", kapitel=1, vers=1, satz="PR")
→ Satzart: V4.1, Syntagmen: P(0 1) 1(1 2) 2(2 9)

bht_sentence_analysis(buch="Jes", kapitel=40, vers=1, satz="a")
→ [different sentence type, different syntagm pattern]
```

#### Find rare verb forms

> "Show me all Hophal (HP) passive verbs in the Torah"

```
bht_search(filters=[{field:"buch", value:"Gen"}, {field:"stamm", value:"HP"}, {field:"wa", value:"11 VERB"}])
bht_search(filters=[{field:"buch", value:"Ex"}, {field:"stamm", value:"HP"}, ...])
... (repeat for Lev, Num, Dt)
```

### Advanced

#### Identify Aramaic sections

> "Which tokens in Daniel are marked as Aramaic rather than Hebrew?"

```
bht_field_info(field="sprache")  → discover language codes
bht_search(filters=[{field:"buch", value:"Dan"}, {field:"sprache", value:"fa:f+"}])
→ Aramaic tokens in Daniel (chapters 2:4b–7:28)
```

#### Hapax legomena search

> "Find lexemes that appear only once in the Hebrew Bible"

Ask the AI to search each lexeme and check its frequency:

```
bht_search(filters=[{field:"lexem", value:"<specific lexeme>"}])
→ If result count = 1, it's a hapax legomenon
```

The AI can iterate through interesting lexemes from a book to find hapax candidates.

#### Cross-book morphological comparison

> "Compare the construct chain patterns (Constructus) between Proverbs and Job"

```
bht_search(filters=[{field:"buch", value:"Spr"}, {field:"wa", value:"12 SUBSTANTIV"}, {field:"ps", value:"C"}])
bht_search(filters=[{field:"buch", value:"Ij"}, {field:"wa", value:"12 SUBSTANTIV"}, {field:"ps", value:"C"}])
→ Compare frequency, lexeme variety, and syntactic positions
```

#### Syntax tree comparison for parallel passages

> "Compare the word-level syntax of Psalm 18 and 2 Samuel 22 (parallel texts)"

```
bht_syntax_tree(buch="Ps", kapitel=18, vers=3, satz="a")
bht_syntax_tree(buch="2Sam", kapitel=22, vers=3, satz="a")
→ Structural differences between the two versions
```

#### Ben Sira manuscript comparison

> "Which chapters of Sirach are preserved in manuscript A vs manuscript B?"

```
bht_list_books()
→ ASir: chapters 2–16,23,27 (17 chapters)
→ BSir: chapters 10–11,15–16,20,30–51 (26 chapters)
→ Overlap: chapters 10,11,15,16 — compare these
```

---

## Tool Reference

| Tool | Purpose | BHt Requests |
|------|---------|:---:|
| **bht_list_books** | List all 47 books with codes and chapter counts | 0 |
| **bht_field_info** | Get valid values for any of 42 search fields | 0–1 |
| **bht_search** | Search tokens by location or morphological filters | 0–1 |
| **bht_token_detail** | Full morphological analysis of a single token | 0–1 |
| **bht_syntax_tree** | Word-level syntactic tree (Wortfügungsebene) | 0–2 |
| **bht_sentence_analysis** | Sentence-level analysis (Satzfügungsebene) | 0–2 |
| **bht_text_annotations** | Textual criticism annotations for a chapter | 0–1 |

**Typical workflow:** `bht_list_books` → `bht_search` → `bht_token_detail` → `bht_syntax_tree`

Every response includes a `quota` field showing daily usage:

```json
{
  "data": [...],
  "quota": {"daily_html_used": 12, "daily_html_limit": 150, "daily_html_remaining": 138}
}
```

---

## Book Codes & Search Fields

### Book Codes (47 books)

```
Torah:      Gen  Ex  Lev  Num  Dt
Prophets:   Jos  Ri  1Sam  2Sam  1Koen  2Koen
            Jes  Jer  Ez
            Hos  Joel  Am  Ob  Jon  Mich  Nah  Hab  Zef  Hag  Sach  Mal
Writings:   Ps  Ij  Spr  Rut  Hl  Koh  Klgl  Est  Dan  Esr  Neh  1Chr  2Chr
Sirach:     ASir  BSir  CSir  DSir  ESir  MSir  QSir  TSir
```

### Common Search Fields

| Field | Description | Example Values |
|-------|-------------|----------------|
| `buch` | Book code | `Gen`, `Ps`, `Jes` |
| `wa` | Part of speech | `11 VERB`, `12 SUBSTANTIV`, `31 PRAEPOSITION` |
| `stamm` | Verbal stem | `G`(Qal), `D`(Piel), `H`(Hiphil), `N`(Niphal) |
| `ps` | Person/Status | `1`, `2`, `3`, `C`(construct), `A`(absolute), `0`(n/a) |
| `gen` | Gender | `M`, `F`, `0`(n/a) |
| `num` | Number | `S`(sg), `P`(pl), `D`(dual), `0`(n/a) |
| `Wurzel` | Root | `BRʾ`, `ʾMR`, `HLK` |
| `lexem` | Lexeme | `baraʾ l+`, `ʾilōhīm l+` |
| `basis` | Base form | `brʾ 1`, `ʾl-h` |
| `sprache` | Language | `fh:f+` (Hebrew), `fa:f+` (Aramaic) |

There are 42 searchable fields in total. Use `bht_field_info(field="<name>")` to discover all valid values for any field.

---

## Rate Limits

This tool accesses a university research server. Built-in limits protect it:

| Limit | Value | Reason |
|-------|-------|--------|
| Request interval | 1 req/s | Server capacity protection |
| Daily HTML requests | 150/day | Token detail, syntax, sentence, annotation pages |
| Daily JSON requests | Unlimited | Search API is lightweight |

These limits are comparable to a researcher manually browsing the site (typically 25–100 pages/day). The daily limit resets at midnight.

When the limit is reached, cached data remains fully accessible — only new HTML fetches are blocked.

---

## License

Code: [MIT](LICENSE)

BHt data: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) (LMU Munich)

---

## 한국어

### 설치

**Python이 없는 경우:** [python.org/downloads](https://www.python.org/downloads/)에서 Python 3.11 이상을 설치하세요.

```bash
pip install bht-mcp
```

### MCP 클라이언트 설정

Claude Desktop, Claude Code, Cursor 등 MCP를 지원하는 AI 클라이언트의 설정에 추가하세요:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

클라이언트를 재시작하면 7개의 BHt 도구가 활성화됩니다.

### 사용 예시

**기초:**
- "창세기 1:1을 단어별로 분석해주세요" → 토큰 검색 + 형태론 상세
- "어근 BRʾ(창조하다)의 모든 용례를 찾아주세요" → 어근 기반 검색
- "창세기 1장의 사본 이본을 보여주세요" → 텍스트 비평 주석

**중급:**
- "전도서에서 동사 어간(stem)별 빈도를 분석해주세요" → 동사 검색 + 어간별 분류
- "창세기 1:1과 이사야 40:1의 문장 구조를 비교해주세요" → 통사 분석 비교
- "토라에서 호팔(Hophal) 수동태 동사를 모두 찾아주세요" → 희귀 동사형 탐색

**고급:**
- "다니엘서에서 아람어 구간의 토큰을 식별해주세요" → 언어 필터(sprache)
- "잠언과 욥기의 연계형(Constructus) 패턴을 비교해주세요" → 형태론 교차 비교
- "시편 18편과 사무엘하 22장의 통사 트리를 비교해주세요" → 병행 본문 분석
- "시라크 사본 A와 B가 겹치는 장을 찾아주세요" → 사본 커버리지 비교

### 작동 방식

로컬에서 실행됩니다. 원격 서버 없음, API 키 없음, 비용 없음.

- 첫 검색 시 해당 책의 전체 토큰을 1회 API 호출로 가져와 로컬 SQLite에 캐시
- 이후 같은 책의 검색은 네트워크 요청 0회
- 형태론 상세(beleg)는 토큰별로 on-demand 캐시
- 대학 서버 보호를 위한 내장 제한: 초당 1요청, 일일 HTML 150건

### 라이선스

코드: MIT | BHt 데이터: CC BY-SA 4.0 (LMU Munich)
