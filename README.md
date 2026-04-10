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

[🇰🇷 한국어](#-한국어)

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
- [Installation & Setup](#installation--setup)
- [Setting Up Your MCP Client](#setting-up-your-mcp-client)
- [Research Scenarios](#research-scenarios)
- [Tool Reference](#tool-reference)
- [Rate Limits](#rate-limits)
- [License](#license)
- [🇰🇷 한국어](#-한국어)

---

## How It Works

```
┌──────────────┐  stdio  ┌──────────────────┐  cache miss  ┌──────────────┐
│  MCP Client  │ ───────→│  bht-mcp         │ ────────────→│  BHt Website │
│  (Claude,    │ ←───────│  (local process) │ ←────────────│ (LMU Munich) │
│  local LLM,  │         │  ┌────────────┐  │              └──────────────┘
│  etc.)       │         │  │ ~/.bht/    │  │
└──────────────┘         │  │ cache.db   │  │  ← local SQLite cache
                         │  └────────────┘  │
                         └──────────────────┘
```

- **Runs entirely on your machine.** No remote server, no API keys, no cost.
- **Progressive caching.** The first search for a book fetches all its tokens in one request. After that, searches in the same book are instant — zero network calls.
- **Respectful.** Built-in rate limits (1 req/s, 150 HTML pages/day) protect the university server. The tool never bulk-scrapes.

---

## Installation & Setup

### Option A: Using uv (recommended)

[uv](https://docs.astral.sh/uv/) is the standard tool for running MCP servers. No separate install step needed — just configure your client.

**Install uv** (one-time):

| Platform | Command |
|----------|---------|
| **macOS** | `brew install uv` |
| **Windows** | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **Linux** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

Then go directly to [Setting Up Your MCP Client](#setting-up-your-mcp-client) below.

### Option B: Using pip

If you prefer a traditional install:

```bash
pip install bht-mcp
```

> **Requires Python 3.11+.** If Python is not installed: [python.org/downloads](https://www.python.org/downloads/) (Windows: check "Add Python to PATH"). macOS: `brew install python`. Linux: `sudo apt install python3 python3-pip`.

---

## Setting Up Your MCP Client

MCP (Model Context Protocol) lets AI assistants use external tools. Choose your client below:

### Claude Desktop

Edit your MCP settings (Settings → Developer → MCP Servers) and add:

**If you installed with uv:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "uvx",
      "args": ["bht-mcp"]
    }
  }
}
```

**If you installed with pip:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "python",
      "args": ["-m", "bht_mcp"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add bht -- uvx bht-mcp
```

Or with pip:

```bash
claude mcp add bht -- python -m bht_mcp
```

### Local LLMs (Open WebUI, llama.cpp, Ollama, etc.)

If your local LLM setup supports MCP, configure it to launch bht-mcp as a stdio subprocess:

**With uv:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "uvx",
      "args": ["bht-mcp"]
    }
  }
}
```

**With pip:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "python",
      "args": ["-m", "bht_mcp"]
    }
  }
}
```

> **Note:** MCP tool calling requires a model that supports function/tool calling. Most 7B+ instruction-tuned models work (Llama 3, Mistral, Qwen, etc.).

### Other MCP-compatible clients

Any client that supports MCP stdio transport can use bht-mcp. Use `uvx bht-mcp` or `python -m bht_mcp` as the server command.

After adding, restart your client. You should see 7 BHt tools available.

---

## Research Scenarios

You don't need to know the tool names or parameters — just describe what you want in natural language. The AI figures out which tools to call.

### 1. Verse analysis — word by word

> "Show me Genesis 1:1 word by word with grammatical analysis"

```
Step 1  AI calls bht_search → finds 11 tokens in Gen 1:1
Step 2  AI calls bht_token_detail on each token → retrieves full morphology

Results:

  Token          Part of Speech        Person  Gender  Number  Stem  Root
  ─────────────  ────────────────────  ──────  ──────  ──────  ────  ────
  b˙             Praeposition          —       —       —       —     —
  rē(ʾ)šīt      Substantiv            —       F       S       —     Rʾš
  barā(ʾ)        Suffixkonjugation     3       M       S       Qal   BRʾ
  ʾïlō*hīm      Substantiv            Abs     M       P       —     ʾL
  ʾȧt            Praeposition          —       —       —       —     —
  ha             Artikel               —       —       —       —     —
  šamaym         Substantiv            —       M       P       —     ŠMM
  w˙             Konjunktion           —       —       —       —     —
  ʾȧt            Praeposition          —       —       —       —     —
  ha             Artikel               —       —       —       —     —
  ʾarṣ           Substantiv            —       F       S       —     ʾRṢ

  BHt requests: 1 search + 11 token details = 12 (cached on repeat)
```

### 2. Cross-book root comparison

> "Compare the use of root BRʾ (create) in Genesis vs Isaiah"

```
Step 1  AI calls bht_search with Wurzel=BRʾ, buch=Gen → 15 tokens
Step 2  AI calls bht_search with Wurzel=BRʾ, buch=Jes → 22 tokens
Step 3  AI calls bht_token_detail on selected tokens → compares stems and forms

Results:

  Genesis — 15 occurrences:
    Qal (G):  barā(ʾ), b˙rō(ʾ), ... — "create" in narrative
    Niphal (N): nibrāʾ — passive "was created"

  Isaiah — 22 occurrences:
    Qal (G):  bōrē(ʾ), barā(ʾ), ... — "create" in prophetic speech
    Piel (D):  appears in Jes 40-55 (Deutero-Isaiah)

  Observation: BRʾ clusters in Gen 1-2 and Jes 40-55, rarely elsewhere.

  BHt requests: 2 searches (0 if books already cached) + N detail fetches
```

### 3. Syntactic structure comparison

> "Compare the syntax of Genesis 1:1 and Isaiah 40:1"

```
Step 1  AI calls bht_sentence_analysis for Gen 1:1 satz=PR
Step 2  AI calls bht_sentence_analysis for Jes 40:1 satz=a
Step 3  AI calls bht_syntax_tree for Gen 1:1 satz=PR → word-level tree

Results:

  Gen 1:1 PR — Sentence type: V4.1
    Syntagms: P(0 1) 1(1 2) 2(2 9)
    Tree: KOORDV → [PV → [PRAEP, ATKV], KONJS → [KONJ, PV → [PRAEP, ATKV]]]
    Pattern: Verb-first, coordinated predicate phrases

  Jes 40:1 a — Sentence type: V1.1
    Syntagms: P(0 2)
    Pattern: Imperative, simpler structure

  BHt requests: 2-4 sentence/tree fetches (resolve may need beleg fetch)
```

### 4. Textual criticism

> "Are there manuscript variants in Genesis 1?"

```
Step 1  AI calls bht_text_annotations for Gen chapter 1

Results:

  Location       Token    Type  Annotation
  ─────────────  ───────  ────  ─────────────────────────────────────────
  Gen 1,7c (3)   kin      TS    als 6d in G; G + 7c text added
  Gen 1,9b (9)   maqōm   T     G reads miqwǟ, MT reads miqwē-m?
  Gen 1,9d (3)   kin      TS    G + 9e text added
  Gen 1,20c (11) šamaym   TS    G + d text added

  Types: TS = text security note, T = text variant
  Manuscripts: G = Greek (Septuagint), MT = Masoretic Text

  BHt requests: 1 (chapter-level, all annotations in one call)
```

### 5. Aramaic section detection in Daniel

> "Which parts of Daniel are in Aramaic rather than Hebrew?"

```
Step 1  AI calls bht_field_info for "sprache" → discovers language codes
Step 2  AI calls bht_search with buch=Dan, sprache=fa:f+ → Aramaic tokens
Step 3  AI calls bht_search with buch=Dan, sprache=fh:f+ → Hebrew tokens

Results:

  Language  Chapters        Token count
  ────────  ──────────────  ───────────
  Hebrew    1:1–2:4a        ~250 tokens
  Aramaic   2:4b–7:28       ~4,800 tokens
  Hebrew    8:1–12:13       ~2,100 tokens

  The AI identifies the well-known bilingual structure of Daniel
  directly from the linguistic data — no manual chapter lookup needed.

  BHt requests: 1 field info + 2 searches (0 if Dan already cached)
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

## 🇰🇷 한국어

AI 어시스턴트에게 히브리어 성경 489,000개 이상의 형태론 분석 토큰을 검색, 분석, 비교하도록 요청하세요 — 채팅 인터페이스에서 바로.

```
사용자: "창세기와 이사야에서 어근 BRʾ(창조하다)의 사용을 비교해줘"
AI:    [각 책에서 어근 필터로 bht_search를 호출하고, 선택된 토큰에 대해
        bht_token_detail을 호출 — 두 책의 형태론 분석, 동사 어간,
        통사적 맥락을 반환합니다]
```

히브리어 전문 지식 없이도 시작할 수 있습니다. AI가 언어학 데이터를 읽고 설명해줍니다.

---

### BHt 소개

BHt (Biblia Hebraica transcripta)는 뮌헨 대학교(LMU Munich)에서 Wolfgang Richter 교수의 지도 아래 관리되는 히브리어 성경 디지털 전사본입니다.

- **489,437개 토큰** — 완전한 형태론 분석 포함
- **Richter 전사 체계** — 라틴 문자 기반 음소 표기 (예: `barā(ʾ)` = בָּרָא)
- **5분류 품사 체계** (Hauptwortart, Nebenwortart, Fügwortart 등)
- **통사 트리** — 단어 수준(Wortfügungsebene) 및 문장 수준(Satzfügungsebene)
- **텍스트 비평 주석** — 그리스어/마소라 사본 이본 데이터
- **시라크 사본 단편 8종** (벤 시라, 카이로 게니자 및 마사다 출토)

---

### 작동 방식

```
┌──────────────┐  stdio  ┌──────────────────┐  cache miss  ┌──────────────┐
│  MCP Client  │ ───────→│  bht-mcp         │ ────────────→│  BHt Website │
│  (Claude,    │ ←───────│  (local process) │ ←────────────│ (LMU Munich) │
│  local LLM,  │         │  ┌────────────┐  │              └──────────────┘
│  etc.)       │         │  │ ~/.bht/    │  │
└──────────────┘         │  │ cache.db   │  │  ← local SQLite cache
                         │  └────────────┘  │
                         └──────────────────┘
```

- **완전히 로컬에서 실행됩니다.** 원격 서버 없음, API 키 없음, 비용 없음.
- **점진적 캐싱.** 특정 책을 처음 검색하면 해당 책의 전체 토큰을 1회 요청으로 가져옵니다. 이후 같은 책의 검색은 즉시 — 네트워크 요청 0회.
- **서버 보호.** 내장 속도 제한(초당 1요청, 일일 HTML 150건)이 대학 서버를 보호합니다. 대량 스크래핑을 하지 않습니다.

---

### 설치 및 설정

#### 방법 A: uv 사용 (권장)

[uv](https://docs.astral.sh/uv/)는 MCP 서버 실행의 표준 도구입니다. 별도 설치 단계 없이 클라이언트 설정만 하면 됩니다.

**uv 설치** (최초 1회):

| 플랫폼 | 방법 |
|--------|------|
| **macOS** | `brew install uv` |
| **Windows** | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **Linux** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

설치 후 아래 [MCP 클라이언트 설정](#mcp-클라이언트-설정)으로 바로 진행하세요.

#### 방법 B: pip 사용

전통적인 방식을 선호하는 경우:

```bash
pip install bht-mcp
```

> **Python 3.11 이상 필요.** Python이 없는 경우: [python.org/downloads](https://www.python.org/downloads/) (Windows: "Add Python to PATH" 체크). macOS: `brew install python`. Linux: `sudo apt install python3 python3-pip`.

---

### MCP 클라이언트 설정

MCP (Model Context Protocol)는 AI 어시스턴트가 외부 도구를 사용할 수 있게 해줍니다. 아래에서 사용 중인 클라이언트를 선택하세요:

#### Claude Desktop

MCP 설정을 편집합니다 (Settings → Developer → MCP Servers):

**uv로 설치한 경우:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "uvx",
      "args": ["bht-mcp"]
    }
  }
}
```

**pip으로 설치한 경우:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "python",
      "args": ["-m", "bht_mcp"]
    }
  }
}
```

#### Claude Code

```bash
claude mcp add bht -- uvx bht-mcp
```

pip 사용 시:

```bash
claude mcp add bht -- python -m bht_mcp
```

#### 로컬 LLM (Open WebUI, llama.cpp, Ollama 등)

로컬 LLM 환경이 MCP를 지원하는 경우, bht-mcp를 stdio 서브프로세스로 설정하세요:

**uv 사용:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "uvx",
      "args": ["bht-mcp"]
    }
  }
}
```

**pip 사용:**
```json
{
  "mcpServers": {
    "bht": {
      "command": "python",
      "args": ["-m", "bht_mcp"]
    }
  }
}
```

> **참고:** MCP tool calling을 사용하려면 함수/도구 호출을 지원하는 모델이 필요합니다. 대부분의 7B+ instruction-tuned 모델이 동작합니다 (Llama 3, Mistral, Qwen 등).

#### 기타 MCP 호환 클라이언트

MCP stdio 전송을 지원하는 모든 클라이언트에서 사용할 수 있습니다. 서버 명령어는 `uvx bht-mcp` 또는 `python -m bht_mcp`입니다.

추가 후 클라이언트를 재시작하면 7개의 BHt 도구가 활성화됩니다.

---

### 연구 시나리오

도구 이름이나 파라미터를 알 필요 없습니다 — 원하는 것을 자연어로 설명하면 AI가 적절한 도구를 호출합니다.

#### 1. 구절 분석 — 단어별 문법

> "창세기 1:1을 단어별로 문법 분석과 함께 보여주세요"

```
단계 1  AI가 bht_search 호출 → Gen 1:1에서 11개 토큰 발견
단계 2  AI가 각 토큰에 bht_token_detail 호출 → 완전한 형태론 조회

결과:

  토큰           품사                  인칭  성    수    어간  어근
  ─────────────  ────────────────────  ────  ────  ────  ────  ────
  b˙             전치사(Praeposition)  —     —     —     —     —
  rē(ʾ)šīt      명사(Substantiv)      —     F     S     —     Rʾš
  barā(ʾ)        접미형(Suffixkonj.)   3     M     S     Qal   BRʾ
  ʾïlō*hīm      명사(Substantiv)      Abs   M     P     —     ʾL
  ʾȧt            전치사(Praeposition)  —     —     —     —     —
  ha             관사(Artikel)         —     —     —     —     —
  šamaym         명사(Substantiv)      —     M     P     —     ŠMM
  w˙             접속사(Konjunktion)   —     —     —     —     —
  ʾȧt            전치사(Praeposition)  —     —     —     —     —
  ha             관사(Artikel)         —     —     —     —     —
  ʾarṣ           명사(Substantiv)      —     F     S     —     ʾRṢ

  BHt 요청: 검색 1회 + 토큰 상세 11회 = 12회 (반복 시 캐시로 0회)
```

#### 2. 책 간 어근 비교

> "창세기와 이사야에서 어근 BRʾ(창조하다)의 사용을 비교해줘"

```
단계 1  AI가 bht_search (Wurzel=BRʾ, buch=Gen) 호출 → 15개 토큰
단계 2  AI가 bht_search (Wurzel=BRʾ, buch=Jes) 호출 → 22개 토큰
단계 3  AI가 선택된 토큰에 bht_token_detail 호출 → 어간과 형태 비교

결과:

  창세기 — 15회 출현:
    칼(Qal, G):  barā(ʾ), b˙rō(ʾ), ... — 서사에서 "창조하다"
    니팔(Niphal, N): nibrāʾ — 수동 "창조되다"

  이사야 — 22회 출현:
    칼(Qal, G):  bōrē(ʾ), barā(ʾ), ... — 예언적 연설에서 "창조하다"
    피엘(Piel, D): Jes 40-55 (제2이사야)에 출현

  관찰: BRʾ는 Gen 1-2와 Jes 40-55에 집중, 다른 곳에서는 드묾.

  BHt 요청: 검색 2회 (책이 이미 캐시되면 0회) + 상세 N회
```

#### 3. 통사 구조 비교

> "창세기 1:1과 이사야 40:1의 통사 구조를 비교해주세요"

```
단계 1  AI가 bht_sentence_analysis (Gen 1:1, satz=PR) 호출
단계 2  AI가 bht_sentence_analysis (Jes 40:1, satz=a) 호출
단계 3  AI가 bht_syntax_tree (Gen 1:1, satz=PR) 호출 → 단어 수준 트리

결과:

  Gen 1:1 PR — 문장 유형: V4.1
    통합소: P(0 1) 1(1 2) 2(2 9)
    트리: KOORDV → [PV → [PRAEP, ATKV], KONJS → [KONJ, PV → [PRAEP, ATKV]]]
    패턴: 동사 선행, 등위 술어구

  Jes 40:1 a — 문장 유형: V1.1
    통합소: P(0 2)
    패턴: 명령형, 단순 구조

  BHt 요청: 문장/트리 가져오기 2-4회 (해석에 beleg 가져오기 필요할 수 있음)
```

#### 4. 텍스트 비평

> "창세기 1장에 사본 이본이 있나요?"

```
단계 1  AI가 bht_text_annotations (Gen, 1장) 호출

결과:

  위치            토큰     유형  주석
  ──────────────  ───────  ────  ─────────────────────────────────────────
  Gen 1,7c (3)    kin      TS    6d로서 G에; G에 7c 텍스트 추가
  Gen 1,9b (9)    maqōm   T     G는 miqwǟ, MT는 miqwē-m?
  Gen 1,9d (3)    kin      TS    G에 9e 텍스트 추가
  Gen 1,20c (11)  šamaym   TS    G에 d 텍스트 추가

  유형: TS = 텍스트 확실성 주석, T = 텍스트 이본
  사본: G = 그리스어(70인역), MT = 마소라 본문

  BHt 요청: 1회 (장 단위, 모든 주석을 한 번에 조회)
```

#### 5. 다니엘서 아람어 구간 식별

> "다니엘서에서 히브리어가 아닌 아람어 구간은?"

```
단계 1  AI가 bht_field_info ("sprache") 호출 → 언어 코드 발견
단계 2  AI가 bht_search (buch=Dan, sprache=fa:f+) 호출 → 아람어 토큰
단계 3  AI가 bht_search (buch=Dan, sprache=fh:f+) 호출 → 히브리어 토큰

결과:

  언어     장               토큰 수
  ───────  ──────────────   ───────────
  히브리어  1:1–2:4a         ~250개
  아람어    2:4b–7:28        ~4,800개
  히브리어  8:1–12:13        ~2,100개

  AI가 잘 알려진 다니엘서의 이중 언어 구조를 언어학 데이터에서
  직접 식별합니다 — 수동 장 조회 없이.

  BHt 요청: 필드 정보 1회 + 검색 2회 (Dan이 이미 캐시되면 0회)
```

---

### 도구 참조

| 도구 | 용도 | BHt 요청 수 |
|------|------|:---:|
| **bht_list_books** | 47개 책 목록 (코드와 장 수 포함) | 0 |
| **bht_field_info** | 42개 검색 필드의 유효한 값 조회 | 0–1 |
| **bht_search** | 위치 또는 형태론 필터로 토큰 검색 | 0–1 |
| **bht_token_detail** | 단일 토큰의 완전한 형태론 분석 | 0–1 |
| **bht_syntax_tree** | 단어 수준 통사 트리 (Wortfügungsebene) | 0–2 |
| **bht_sentence_analysis** | 문장 수준 분석 (Satzfügungsebene) | 0–2 |
| **bht_text_annotations** | 장 단위 텍스트 비평 주석 | 0–1 |

**일반적인 워크플로우:** `bht_list_books` → `bht_search` → `bht_token_detail` → `bht_syntax_tree`

모든 응답에 일일 사용량을 보여주는 `quota` 필드가 포함됩니다:

```json
{
  "data": [...],
  "quota": {"daily_html_used": 12, "daily_html_limit": 150, "daily_html_remaining": 138}
}
```

---

### 사용 제한

이 도구는 대학 연구 서버에 접근합니다. 내장된 제한이 서버를 보호합니다:

| 제한 | 값 | 이유 |
|------|---|------|
| 요청 간격 | 초당 1회 | 서버 용량 보호 |
| 일일 HTML 요청 | 150건/일 | 토큰 상세, 통사, 문장, 주석 페이지 |
| 일일 JSON 요청 | 무제한 | 검색 API는 경량 |

이 제한은 연구자가 직접 사이트를 탐색하는 수준(보통 하루 25–100 페이지)과 동등합니다. 일일 제한은 자정에 초기화됩니다.

제한에 도달하면 캐시된 데이터는 여전히 완전히 접근 가능합니다 — 새로운 HTML 가져오기만 차단됩니다.

---

### 라이선스

코드: [MIT](LICENSE)

BHt 데이터: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) (LMU Munich)
