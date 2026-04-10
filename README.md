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
- [Rate Limits](#rate-limits)
- [License](#license)
- [한국어](#한국어)

---

## How It Works

```
┌──────────────┐  stdio  ┌──────────────────┐  cache miss  ┌─────────────┐
│  MCP Client  │ ───────→│  bht-mcp         │ ───────────→│  BHt Website │
│  (Claude,    │ ←───────│  (local process) │ ←───────────│  (LMU Munich)│
│   local LLM, │         │  ┌────────────┐  │              └─────────────┘
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

### Claude Desktop

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

### Claude Code

Run in your terminal:

```bash
claude mcp add bht -- bht-mcp
```

Or manually edit `~/.claude/claude_desktop_config.json` with the JSON above.

### Local LLMs (Open WebUI, llama.cpp, Ollama, etc.)

If your local LLM setup supports MCP, configure it to launch `bht-mcp` as a stdio subprocess. The server command is:

```bash
bht-mcp
```

For frameworks that accept an MCP server config:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

> **Note:** MCP tool calling requires a model that supports function/tool calling. Most 7B+ instruction-tuned models work (Llama 3, Mistral, Qwen, etc.).

### Other MCP-compatible clients

Any client that supports MCP stdio transport can use bht-mcp. The server command is simply `bht-mcp`.

After adding, restart your client. You should see 7 BHt tools available.

---

## Research Scenarios

You don't need to know the tool names or parameters — just describe what you want in natural language. The AI figures out which tools to call.

### Getting Started

#### Read a verse

> "Show me Genesis 1:1 word by word with grammatical analysis"

The AI finds all tokens in the verse, then retrieves morphology for each:

```
barā(ʾ) — Suffixkonjugation, 3rd person masc. singular, Qal stem, root BRʾ
ʾïlō*hīm — Substantiv, masc. plural, base ʾl-h
ʾȧt — Praeposition
ha=šamaym — Substantiv with article, masc. plural
```

#### Explore a root

> "Find all forms of root ʾMR (say/speak) in the Psalms"

The AI searches for all tokens with this root in the specified book and presents the results grouped by form.

#### Check manuscript variants

> "Are there textual variants in Genesis 1?"

```
→ Gen 1,7c — "kin": differs in Greek (G); G adds 7c text
→ Gen 1,9b — "maqōm": G reads miqwǟ, MT reads miqwē-m?
```

### Intermediate

#### Verbal stem distribution in a book

> "What verbal stems appear in Ecclesiastes, and how frequent are they?"

The AI searches for all verbs in Kohelet, retrieves their stem information, and presents frequency statistics:

```
→ G (Qal): 312, D (Piel): 45, H (Hiphil): 67, N (Niphal): 28, ...
```

#### Compare sentence structure across books

> "Compare the syntactic structure of Gen 1:1 and the opening of Isaiah 40:1"

The AI retrieves sentence-level analysis for both verses and highlights structural differences — sentence type, syntagm patterns, and clause relationships.

#### Find rare verb forms

> "Show me all Hophal (HP) passive verbs in the Torah"

The AI searches each Torah book for Hophal stems and compiles a comprehensive list across Genesis through Deuteronomy.

### Advanced

#### Identify Aramaic sections

> "Which tokens in Daniel are marked as Aramaic rather than Hebrew?"

The AI discovers the language codes available in BHt, then filters Daniel's tokens by language — revealing the Aramaic sections (chapters 2:4b–7:28).

#### Hapax legomena search

> "Find lexemes that appear only once in the Hebrew Bible"

The AI iterates through lexemes from a book, checking each one's frequency across the entire corpus. Lexemes with exactly one occurrence are flagged as hapax legomena.

#### Cross-book morphological comparison

> "Compare the construct chain patterns (Constructus) between Proverbs and Job"

The AI searches both books for construct-state nouns, then compares frequency, lexeme variety, and syntactic positions to reveal stylistic differences.

#### Syntax tree comparison for parallel passages

> "Compare the word-level syntax of Psalm 18 and 2 Samuel 22 (parallel texts)"

The AI retrieves syntactic trees for matching verses in both books and highlights structural divergences between the two textual traditions.

#### Ben Sira manuscript comparison

> "Which chapters of Sirach are preserved in manuscript A vs manuscript B?"

The AI queries the book list to show manuscript coverage:

```
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
┌──────────────┐  stdio  ┌──────────────────┐  캐시 미스   ┌──────────────┐
│  MCP 클라이언트│ ───────→│  bht-mcp         │ ──────────→│  BHt 웹사이트  │
│  (Claude,    │ ←───────│  (로컬 프로세스)    │ ←──────────│  (LMU Munich) │
│  로컬 LLM 등) │         │  ┌────────────┐  │             └──────────────┘
└──────────────┘         │  │ ~/.bht/    │  │
                         │  │ cache.db   │  │  ← 로컬 SQLite 캐시
                         │  └────────────┘  │
                         └──────────────────┘
```

- **완전히 로컬에서 실행됩니다.** 원격 서버 없음, API 키 없음, 비용 없음.
- **점진적 캐싱.** 특정 책을 처음 검색하면 해당 책의 전체 토큰을 1회 요청으로 가져옵니다. 이후 같은 책의 검색은 즉시 — 네트워크 요청 0회.
- **서버 보호.** 내장 속도 제한(초당 1요청, 일일 HTML 150건)이 대학 서버를 보호합니다. 대량 스크래핑을 하지 않습니다.

---

### 설치

#### 1. Python 설치 (이미 설치된 경우 건너뛰기)

먼저 확인:

```bash
python3 --version
```

`Python 3.11` 이상이면 2단계로 건너뛰세요.

**Python이 설치되어 있지 않은 경우:**

| 플랫폼 | 방법 |
|--------|------|
| **macOS** | `brew install python` ([Homebrew](https://brew.sh/) 필요) |
| **macOS (Homebrew 없음)** | [python.org/downloads](https://www.python.org/downloads/)에서 다운로드 |
| **Windows** | [python.org/downloads](https://www.python.org/downloads/)에서 다운로드. 설치 시 "Add Python to PATH" 체크. |
| **Linux (Debian/Ubuntu)** | `sudo apt install python3 python3-pip` |

#### 2. bht-mcp 설치

```bash
pip install bht-mcp
```

설치 확인:

```bash
bht-mcp --help
```

`pip`이 인식되지 않으면 `pip3`를 사용하세요.

---

### MCP 클라이언트 설정

MCP (Model Context Protocol)는 AI 어시스턴트가 외부 도구를 사용할 수 있게 해줍니다. AI 클라이언트에 bht-mcp를 등록해야 합니다. 아래에서 사용 중인 클라이언트를 선택하세요:

#### Claude Desktop

MCP 설정을 편집합니다 (Settings → Developer → MCP Servers):

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

#### Claude Code

터미널에서 실행:

```bash
claude mcp add bht -- bht-mcp
```

또는 `~/.claude/claude_desktop_config.json`에 위의 JSON을 직접 추가할 수도 있습니다.

#### 로컬 LLM (Open WebUI, llama.cpp, Ollama 등)

로컬 LLM 환경이 MCP를 지원하는 경우, `bht-mcp`를 stdio 서브프로세스로 실행하도록 설정하세요. 서버 명령어:

```bash
bht-mcp
```

MCP 서버 설정을 받는 프레임워크의 경우:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

> **참고:** MCP tool calling을 사용하려면 함수/도구 호출을 지원하는 모델이 필요합니다. 대부분의 7B+ instruction-tuned 모델이 동작합니다 (Llama 3, Mistral, Qwen 등).

#### 기타 MCP 호환 클라이언트

MCP stdio 전송을 지원하는 모든 클라이언트에서 사용할 수 있습니다. 서버 명령어는 `bht-mcp`입니다.

추가 후 클라이언트를 재시작하면 7개의 BHt 도구가 활성화됩니다.

---

### 연구 시나리오

도구 이름이나 파라미터를 알 필요 없습니다 — 원하는 것을 자연어로 설명하면 AI가 적절한 도구를 호출합니다.

#### 기초

##### 구절 분석

> "창세기 1:1을 단어별로 문법 분석과 함께 보여주세요"

AI가 해당 절의 모든 토큰을 찾고, 각각의 형태론을 조회합니다:

```
barā(ʾ) — Suffixkonjugation, 남성 단수 3인칭, 칼(Qal) 어간, 어근 BRʾ
ʾïlō*hīm — Substantiv, 남성 복수, 기초형 ʾl-h
ʾȧt — 전치사(Praeposition)
ha=šamaym — 관사 포함 Substantiv, 남성 복수
```

##### 어근 탐색

> "시편에서 어근 ʾMR (말하다)의 모든 형태를 찾아주세요"

AI가 해당 책에서 이 어근의 모든 토큰을 검색하고, 형태별로 그룹화하여 결과를 제시합니다.

##### 사본 이본 확인

> "창세기 1장에 텍스트 비평 주석이 있나요?"

```
→ Gen 1,7c — "kin": 그리스어(G)와 차이; G에 7c 텍스트 추가
→ Gen 1,9b — "maqōm": G는 miqwǟ, MT는 miqwē-m?
```

#### 중급

##### 동사 어간 분포 분석

> "전도서에 어떤 동사 어간이 나타나며, 빈도는 어떤가요?"

AI가 코헬렛의 모든 동사를 검색하고, 어간 정보를 조회하여 빈도 통계를 제시합니다:

```
→ G (칼/Qal): 312, D (피엘/Piel): 45, H (히필/Hiphil): 67, N (니팔/Niphal): 28, ...
```

##### 책 간 문장 구조 비교

> "창세기 1:1과 이사야 40:1의 통사 구조를 비교해주세요"

AI가 두 구절의 문장 수준 분석을 가져와 구조적 차이를 강조합니다 — 문장 유형, 통합소(Syntagmen) 패턴, 절 관계.

##### 희귀 동사형 탐색

> "토라에서 호팔(Hophal, HP) 수동태 동사를 모두 찾아주세요"

AI가 창세기부터 신명기까지 각 토라 책에서 호팔 어간을 검색하고 종합 목록을 작성합니다.

#### 고급

##### 아람어 구간 식별

> "다니엘서에서 히브리어가 아닌 아람어로 표시된 토큰은?"

AI가 BHt에서 사용 가능한 언어 코드를 발견한 후, 다니엘서의 토큰을 언어별로 필터링합니다 — 아람어 구간(2:4b–7:28장)이 드러납니다.

##### 하팍스 레고메논(Hapax legomenon) 탐색

> "히브리어 성경에서 단 한 번만 등장하는 어휘소를 찾아주세요"

AI가 특정 책의 어휘소를 순회하며 전체 코퍼스에서 각각의 빈도를 확인합니다. 정확히 1회 출현하는 어휘소가 하팍스 레고메논으로 표시됩니다.

##### 책 간 형태론 비교

> "잠언과 욥기의 연계형(Constructus) 패턴을 비교해주세요"

AI가 두 책에서 연계형 명사를 검색한 후, 빈도, 어휘소 다양성, 통사적 위치를 비교하여 문체적 차이를 드러냅니다.

##### 병행 본문의 통사 트리 비교

> "시편 18편과 사무엘하 22장의 단어 수준 통사 구조를 비교해주세요 (병행 본문)"

AI가 두 책의 대응 절에서 통사 트리를 가져와 두 텍스트 전승 사이의 구조적 차이를 강조합니다.

##### 벤 시라 사본 비교

> "시라크 사본 A와 사본 B에 보존된 장은 각각 어떤 것인가요?"

AI가 책 목록을 조회하여 사본 커버리지를 보여줍니다:

```
→ ASir: 2–16, 23, 27장 (17개 장)
→ BSir: 10–11, 15–16, 20, 30–51장 (26개 장)
→ 겹치는 장: 10, 11, 15, 16 — 이들을 비교
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
