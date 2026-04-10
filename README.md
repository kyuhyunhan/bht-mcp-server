# bht-mcp

MCP server for the [BHt (Biblia Hebraica transcripta)](https://www.bht.gwi.uni-muenchen.de/) Hebrew Bible database at LMU Munich.

Gives AI assistants direct access to 489,000+ morphologically analyzed Hebrew Bible tokens — search by book, root, part of speech, or any of 42 linguistic fields.

[한국어 안내는 아래에 있습니다.](#한국어)

## Quick Start

**1. Verify Python**

```bash
python3 --version  # 3.11+
```

**2. Install**

```bash
pip install bht-mcp
```

**3. Configure your MCP client**

Add to your client's MCP server configuration:

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

That's it. The server runs locally via stdio — no API keys, no remote server, no cost.

## What You Can Do

### Verse Analysis

> "Show me Genesis 1:1 word by word"

```
bht_search(filters=[{field:"buch", value:"Gen"}, {field:"kapitel", value:"1"}, {field:"vers", value:"1"}])
→ 11 tokens: b˙, rē(ʾ)šīt, barā(ʾ), ʾïlō*hīm, ʾȧt, ha, šamaym, w˙, ʾȧt, ha, ʾarṣ

bht_token_detail(buch="Gen", beleg_nr=3)
→ barā(ʾ): Suffixkonjugation, 3ms, Qal, root BRʾ, meaning "fac,prod"
```

### Vocabulary Study

> "Find all occurrences of root BRʾ (create)"

```
bht_search(filters=[{field:"Wurzel", value:"BRʾ"}])
→ All tokens derived from this root across the entire Hebrew Bible
```

### Grammar Patterns

> "Show all Qal verbs in Psalms"

```
bht_search(filters=[{field:"buch", value:"Ps"}, {field:"wa", value:"11 VERB"}, {field:"stamm", value:"G"}])
```

### Syntax

> "What's the syntactic structure of Genesis 1:1?"

```
bht_syntax_tree(buch="Gen", kapitel=1, vers=1, satz="PR")
→ KOORDV → [PV → [PRAEP, ATKV → [ATK, SUB]], KONJS → [KONJ, PV → [...]]]

bht_sentence_analysis(buch="Gen", kapitel=1, vers=1, satz="PR")
→ Satzart: V4.1, Syntagmen: P(0 1) 1(1 2) 2(2 9)
```

### Textual Criticism

> "Are there manuscript variants in Genesis 1?"

```
bht_text_annotations(buch="Gen", kapitel=1)
→ 4 annotations including Greek/MT variants
```

## Tools

| Tool | Purpose | BHt Requests |
|------|---------|:---:|
| **bht_list_books** | List all 47 books with codes and chapter counts | 0 |
| **bht_field_info** | Get valid values for any of 42 search fields | 0–1 |
| **bht_search** | Search tokens by location or morphological filters | 0–1 |
| **bht_token_detail** | Full morphological analysis of a single token | 0–1 |
| **bht_syntax_tree** | Word-level syntactic tree (Wortfügungsebene) | 0–2 |
| **bht_sentence_analysis** | Sentence-level analysis (Satzfügungsebene) | 0–2 |
| **bht_text_annotations** | Textual criticism annotations for a chapter | 0–1 |

### Book Codes

```
Torah:    Gen Ex Lev Num Dt
Prophets: Jos Ri 1Sam 2Sam 1Koen 2Koen Jes Jer Ez
          Hos Joel Am Ob Jon Mich Nah Hab Zef Hag Sach Mal
Writings: Ps Ij Spr Rut Hl Koh Klgl Est Dan Esr Neh 1Chr 2Chr
Sirach:   ASir BSir CSir DSir ESir MSir QSir TSir
```

### Common Search Fields

| Field | Description | Example Values |
|-------|-------------|----------------|
| `buch` | Book code | `Gen`, `Ps`, `Jes` |
| `wa` | Part of speech | `11 VERB`, `12 SUBSTANTIV`, `31 PRAEPOSITION` |
| `stamm` | Verbal stem | `G`(Qal), `D`(Piel), `H`(Hiphil), `N`(Niphal) |
| `ps` | Person | `1`, `2`, `3`, `0`(n/a) |
| `gen` | Gender | `M`, `F`, `0`(n/a) |
| `num` | Number | `S`(sg), `P`(pl), `D`(dual), `0`(n/a) |
| `Wurzel` | Root | `BRʾ`, `ʾMR`, `HLK` |
| `lexem` | Lexeme | `baraʾ l+`, `ʾilōhīm l+` |
| `basis` | Base form | `brʾ 1`, `ʾl-h` |

Use `bht_field_info(field="wa")` to get the full list of valid values for any field.

## How It Works

```
┌──────────────┐  stdio  ┌──────────────────┐  cache miss  ┌─────────────┐
│  MCP Client  │ ───────→│  bht-mcp         │ ───────────→│  BHt Website │
│  (your AI)   │ ←───────│  (local process) │ ←───────────│  (LMU Munich)│
└──────────────┘         │  ┌────────────┐  │              └─────────────┘
                         │  │ ~/.bht/    │  │
                         │  │ cache.db   │  │  ← local SQLite cache
                         │  └────────────┘  │
                         └──────────────────┘
```

**Progressive caching:** The first search for a book fetches all its tokens (one API call). Subsequent searches for the same book use the local cache — zero network requests. Morphological detail is cached per-token as you explore.

## Rate Limits

This tool accesses a university research server. Built-in limits protect it:

| Limit | Value | Reason |
|-------|-------|--------|
| Request interval | 1 req/s | Server capacity protection |
| Daily HTML requests | 150/day | Beleg, tree, sentence, annotation pages |
| Daily JSON requests | Unlimited | Search API is lightweight |

These limits are comparable to a researcher manually browsing the site (~25–100 pages/day). The 150/day limit resets at midnight.

**Every tool response includes a `quota` field** showing current usage:

```json
{
  "data": [...],
  "quota": {"daily_html_used": 12, "daily_html_limit": 150, "daily_html_remaining": 138}
}
```

## About BHt

BHt (Biblia Hebraica transcripta) is a digital transcription of the Hebrew Bible maintained at LMU Munich under the direction of Prof. Wolfgang Richter. It features:

- **489,437 tokens** with full morphological analysis
- **Richter transcription system** (Latin-script phonemic representation)
- **5-class part-of-speech system** (Hauptwortart, Nebenwortart, Fügwortart, etc.)
- **Syntactic trees** at word-level (Wortfügungsebene) and sentence-level (Satzfügungsebene)
- **Textual criticism annotations** with manuscript variant data

The transcription uses a distinctive system where e.g. `barā(ʾ)` represents the Hebrew word בָּרָא, with morphophonemic detail not found in other digital Hebrew Bible projects.

## License

Code: [MIT](LICENSE)

BHt data: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) (LMU Munich)

---

## 한국어

### 설치

```bash
pip install bht-mcp
```

### MCP 클라이언트 설정

```json
{
  "mcpServers": {
    "bht": {
      "command": "bht-mcp"
    }
  }
}
```

### 사용 예시

**구절 분석:** "창세기 1:1을 단어별로 보여주세요"
- `bht_search`로 토큰 검색 → `bht_token_detail`로 형태론 상세 확인

**어휘 연구:** "어근 BRʾ(창조하다)의 모든 용례를 찾아주세요"
- `bht_search(filters=[{field:"Wurzel", value:"BRʾ"}])`

**문법 패턴:** "시편의 모든 칼(Qal) 동사를 찾아주세요"
- `bht_search(filters=[{field:"buch", value:"Ps"}, {field:"wa", value:"11 VERB"}, {field:"stamm", value:"G"}])`

**통사론:** "창세기 1:1의 문장 구조는?"
- `bht_syntax_tree`로 단어 수준 통사 트리, `bht_sentence_analysis`로 문장 수준 분석

**텍스트 비평:** "창세기 1장에 사본 이본이 있나요?"
- `bht_text_annotations(buch="Gen", kapitel=1)` → 그리스어/마소라 사본 차이

### 작동 방식

로컬에서 실행됩니다. 원격 서버 없음, API 키 없음, 비용 없음.

- 첫 검색 시 해당 책의 전체 토큰을 1회 API 호출로 가져와 로컬 SQLite에 캐시
- 이후 같은 책의 검색은 네트워크 요청 0회
- 형태론 상세(beleg)는 토큰별로 on-demand 캐시

### 제한사항

대학 연구 서버를 보호하기 위한 내장 제한:
- 초당 1요청 (서버 부하 보호)
- 일일 HTML 요청 150건 (beleg, tree, sentence, annotation)
- 일일 JSON 요청 무제한 (검색 API는 경량)

### 라이선스

코드: MIT | BHt 데이터: CC BY-SA 4.0 (LMU Munich)
