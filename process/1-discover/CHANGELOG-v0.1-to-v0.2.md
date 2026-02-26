# BBDSL v0.1 → v0.2 修訂摘要

## 一句話總結

> v0.1 是一個「能用 YAML 寫叫牌制度」的草案；
> v0.2 是一個「能被機器驗證、能匯出到 BBO、能被 AI 消費、能感知情境」的規格。

---

## 十大修訂項目

### 1. 座位與身價成為一等公民
**問題**：v0.1 完全沒有座位/身價概念，但實際上第三家開叫、有身價的弱二等差異巨大。
**來源**：BBOalert 支援座位/身價條件。
**方案**：
```yaml
# 新增頂層 contexts 區塊
contexts:
  third_seat_nv:
    seat: 3rd
    vulnerability: none

# 任何叫牌節點可附加 context_overrides
context_overrides:
  - context: { seat: 3rd, vulnerability: none }
    meaning:
      hand: { hcp: { min: 15 } }
```

### 2. 對手行為分支 (when_opponent)
**問題**：v0.1 只描述無競叫的序列，完全忽略了競叫情境。
**來源**：BBOalert 的萬用字元（`--` / `__`）。
**方案**：
```yaml
responses:
  - when_opponent: pass
    bids: [...]
  - when_opponent: double
    bids: [...]
  - when_opponent: bid
    bids: [...]
```

### 3. 對稱性語法糖 (foreach_suit)
**問題**：v0.1 中 Jacoby Transfer 要把 2D→H 和 2H→S 分別寫兩次。
**來源**：bidding-system-as-code 的 `Major.suits.forEach` 做法。
**方案**：
```yaml
foreach_suit:
  variable: M
  over: majors          # ["H", "S"]
bid: "1${M}"
# 自動展開為 1H 和 1S 兩組定義
```

### 4. Convention 參數化與互斥宣告
**問題**：v0.1 的 Convention 是靜態的，無法處理「普通 Stayman vs Puppet Stayman」這種變體。
**來源**：BML 的 COPY/PASTE 機制啟發。
**方案**：
```yaml
conventions:
  stayman:
    parameters:
      nt_bid: "1NT"           # 可被引用者覆寫
      garbage_stayman: true
    conflicts_with: ["conv-puppet-stayman"]

# 引用時帶參數
conventions_applied:
  - ref: "conv-stayman"
    parameters: { nt_bid: "1NT", garbage_stayman: true }
```

### 5. forcing 語義層級
**問題**：v0.1 有 forcing 欄位但只有 "none" / "one_round" / "game"，不夠完整。
**來源**：橋牌語義的核心需求。
**方案**：六級 forcing 語義：
- `signoff`：止叫
- `none`：不迫叫
- `invitational`：邀請
- `one_round`：一輪迫叫
- `game`：迫叫成局
- `slam`：迫叫滿貫

### 6. 多語系 (I18nString)
**問題**：v0.1 的 description 是單一字串。
**來源**：BBOalert 的 Alias 多語機制。
**方案**：所有 description 欄位支援 I18nString 型別：
```yaml
description:
  zh-TW: "強梅花開叫"
  en: "Strong club opening"
  ja: "ストロングクラブオープニング"
```

### 7. 牌套品質定義
**問題**：v0.1 只有 HCP 和花色長度約束，無法表達「好套」「弱套」等品質概念。
**來源**：實際橋牌的弱二開叫對花色品質有嚴格要求。
**方案**：
```yaml
definitions:
  suit_qualities:
    good:
      top3_honors: { min: 2 }    # AKQ 中至少兩張
    strong:
      top3_honors: { min: 2 }
      min_length: 6

# 使用時
hand:
  suit_quality:
    hearts: { ref: "good" }
```

### 8. 匯出生態系 (export)
**問題**：v0.1 沒有考慮輸出。
**來源**：BML 輸出 HTML/LaTeX/BSS；BBOalert 是事實上的線上對打格式。
**方案**：
```yaml
export:
  bboalert: { enabled: true }
  bml: { enabled: true, output_format: html }
  convention_card: { enabled: true, format: wbf }
```

### 9. 完成度標示 (completeness)
**問題**：v0.1 的漸進式定義沒有明確的追蹤機制。
**來源**：BBDSL 作為通用工具需要讓使用者知道哪裡還沒寫完。
**方案**：
```yaml
system:
  completeness:
    openings: complete
    responses_to_1c: complete
    defensive: partial
    slam_bidding: todo
```

### 10. 強化驗證規則
**問題**：v0.1 只有 5 條驗證規則。
**來源**：AI 可驗證性是核心差異化。
**方案**：擴充至 10 條，新增：
- `val-forcing-consistency`：forcing 序列一致性
- `val-convention-conflicts`：互斥 Convention 檢查
- `val-seat-vulnerability`：座位/身價覆寫衝突
- `val-foreach-expansion`：展開後叫品衝突
- 所有規則含 `scope` 欄位限定檢查範圍

---

## 不變的核心設計

以下 v0.1 的設計在 v0.2 中保持不變：
- YAML 宣告式格式
- 巢狀叫牌樹結構
- Convention ref 引用機制
- HandConstraint 基本模型（HCP + 花色長度）
- Pattern 定義與引用
- 繼承（base）機制
- JSON Schema 驗證

---

## 遷移指南

| v0.1 寫法 | v0.2 寫法 | 說明 |
|-----------|-----------|------|
| `description: "文字"` | `description: { zh-TW: "文字", en: "text" }` | 多語系（或保持單一字串也合法） |
| `forcing: "one_round"` | `forcing: one_round` | 不變，但新增 signoff / invitational |
| 無 | `context_overrides: [...]` | 新增座位/身價覆寫 |
| 無 | `when_opponent: pass` | 新增對手行為分支 |
| 重複寫 1H / 1S | `foreach_suit: { variable: M, over: majors }` | 對稱性語法糖 |
| 無 | `export: { bboalert: ... }` | 新增匯出設定 |
| 無 | `completeness: { ... }` | 新增完成度追蹤 |
