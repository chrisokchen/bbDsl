# BBDSL - Bridge Bidding Description Specification Language

## 版本: 0.1.0-draft
## 設計目標

1. **通用性**：能描述任意叫牌制度（精準制、自然制、波蘭梅花、藍梅花等）
2. **教學友善**：支援視覺化呈現叫牌邏輯樹
3. **機器可驗證**：支援一致性檢查、遺漏偵測、衝突檢測
4. **AI 可讀**：作為 AI 對練的制度知識庫
5. **社群協作**：模組化設計，約定（Convention）可獨立定義與組合

---

## 核心概念模型

```
System (制度)
  ├── Metadata (元資料)
  ├── Definitions (全域定義)
  │     ├── HandPatterns (牌型模式)
  │     ├── StrengthRanges (牌力區間)
  │     └── Conventions (特約模組)
  ├── Openings (開叫)
  │     └── Sequences (後續發展)
  ├── Defensive (防禦性叫牌)
  │     ├── Overcalls (爭叫)
  │     ├── Doubles (賭倍)
  │     └── Balancing (平衡位叫牌)
  └── Competitive (競叫對策)
        ├── AfterOpponentOvercall
        ├── AfterOpponentDouble
        └── AfterOpponentPreempt
```

---

## Schema 規格

### 頂層結構

```yaml
bbdsl: "0.1"

system:
  name: "精準制 (Precision Club)"
  version: "1.0.0"
  authors:
    - name: "C.C. Wei"
      contact: ""
  description: "經典精準制，強梅花開叫"
  base: null                    # 可繼承其他制度
  locale: "zh-TW"              # 支援多語系

# ========================================
# 全域定義區
# ========================================
definitions:

  # --- 牌力定義 ---
  strength:
    hcp:                        # 大牌點 (A=4, K=3, Q=2, J=1)
      min: 0
      max: 37
    controls:                   # 控制 (A=2, K=1)
      min: 0
      max: 12
    losing_tricks:              # 失墩計算
      min: 0
      max: 12

  # --- 牌型模式 (可重用) ---
  patterns:
    balanced:
      description: "平均牌型"
      shapes:
        - "4-3-3-3"
        - "4-4-3-2"
        - "5-3-3-2"             # 5332 是否算平均可由制度決定
      exclude_shapes: []

    semi_balanced:
      description: "半平均牌型"
      shapes:
        - "5-4-2-2"
        - "6-3-2-2"

    single_suited:
      description: "單花色套"
      constraints:
        - suit: any
          min_length: 6

    two_suited:
      description: "雙花色套"
      constraints:
        - suits: [any, any]
          min_length: [5, 4]    # 至少 5-4 配合

  # --- 花色優先序 ---
  suit_rank:
    - { symbol: "C", name: "梅花", aliases: ["♣", "clubs"] }
    - { symbol: "D", name: "方塊", aliases: ["♦", "diamonds"] }
    - { symbol: "H", name: "紅心", aliases: ["♥", "hearts"] }
    - { symbol: "S", name: "黑桃", aliases: ["♠", "spades"] }
    - { symbol: "NT", name: "無王", aliases: ["notrump", "無將"] }

# ========================================
# 特約模組 (Convention Modules)
# ========================================
conventions:

  stayman:
    id: "conv-stayman"
    name: "Stayman"
    description: "對 1NT/2NT 開叫後問四張高花"
    version: "standard"
    trigger:
      after: ["1NT", "2NT"]
      bid: "2C"                 # 或 3C (對 2NT)
    requires: []                # 前置約定依賴
    responses:
      - bid: "2D"
        meaning:
          description: "否認持有四張高花"
          hand:
            four_card_major: false
      - bid: "2H"
        meaning:
          description: "四張紅心（可能也有四張黑桃）"
          hand:
            hearts: { min: 4 }
      - bid: "2S"
        meaning:
          description: "四張黑桃，非四張紅心"
          hand:
            spades: { min: 4 }
            hearts: { max: 3 }

  transfers:
    id: "conv-jacoby-transfer"
    name: "乔乗轉換叫 (Jacoby Transfer)"
    description: "對 NT 開叫後的轉換叫"
    trigger:
      after: ["1NT", "2NT"]
    bids:
      - bid: "2D"
        meaning:
          transfer_to: "H"
          hand:
            hearts: { min: 5 }
      - bid: "2H"
        meaning:
          transfer_to: "S"
          hand:
            spades: { min: 5 }

# ========================================
# 開叫定義
# ========================================
openings:

  - bid: "1C"
    id: "open-1c"
    meaning:
      description: "強梅花開叫"
      hand:
        hcp: { min: 16 }
        shape: any              # 任何牌型
      alertable: true
      artificial: true          # 人工叫品
    responses:
      - bid: "1D"
        id: "resp-1c-1d"
        meaning:
          description: "否認叫（消極回應）"
          hand:
            hcp: { min: 0, max: 7 }
          artificial: true
          alertable: true
        continuations:
          # 開叫者的再叫
          - bid: "1H"
            by: opener
            meaning:
              description: "四張以上紅心，16+ HCP"
              hand:
                hearts: { min: 4 }
          - bid: "1S"
            by: opener
            meaning:
              description: "四張以上黑桃，16+ HCP"
              hand:
                spades: { min: 4 }
          - bid: "1NT"
            by: opener
            meaning:
              description: "平均牌型，16-18 HCP"
              hand:
                hcp: { min: 16, max: 18 }
                shape: { ref: "balanced" }
          - bid: "2C"
            by: opener
            meaning:
              description: "五張以上梅花，16+ HCP"
              hand:
                clubs: { min: 5 }
          - bid: "2NT"
            by: opener
            meaning:
              description: "平均牌型，22-23 HCP"
              hand:
                hcp: { min: 22, max: 23 }
                shape: { ref: "balanced" }
          - bid: "3NT"
            by: opener
            meaning:
              description: "平均牌型，24+ HCP"
              hand:
                hcp: { min: 24 }
                shape: { ref: "balanced" }

      - bid: "1H"
        id: "resp-1c-1h"
        meaning:
          description: "8+ HCP，五張以上紅心"
          hand:
            hcp: { min: 8 }
            hearts: { min: 5 }
          alertable: false

      - bid: "1S"
        id: "resp-1c-1s"
        meaning:
          description: "8+ HCP，五張以上黑桃"
          hand:
            hcp: { min: 8 }
            spades: { min: 5 }

      - bid: "1NT"
        id: "resp-1c-1nt"
        meaning:
          description: "8-13 HCP，平均牌型，無五張高花"
          hand:
            hcp: { min: 8, max: 13 }
            shape: { ref: "balanced" }
            hearts: { max: 4 }
            spades: { max: 4 }

      - bid: "2C"
        id: "resp-1c-2c"
        meaning:
          description: "8+ HCP，五張以上梅花"
          hand:
            hcp: { min: 8 }
            clubs: { min: 5 }

      - bid: "2D"
        id: "resp-1c-2d"
        meaning:
          description: "8+ HCP，五張以上方塊"
          hand:
            hcp: { min: 8 }
            diamonds: { min: 5 }

      - bid: "2NT"
        id: "resp-1c-2nt"
        meaning:
          description: "14+ HCP，平均牌型"
          hand:
            hcp: { min: 14 }
            shape: { ref: "balanced" }

  - bid: "1D"
    id: "open-1d"
    meaning:
      description: "方塊開叫，可能只有兩張"
      hand:
        hcp: { min: 11, max: 15 }
        shape:
          not_ref: "balanced"   # 非平均牌型時需 4+ 方塊
          # 或平均牌型 11-13
        clubs: { max: 4 }       # 梅花不超過方塊
      notes: |
        精準制中 1D 開叫較為複雜：
        - 11-15 HCP
        - 可能只有 2 張方塊（當 4-4-3-2 牌型，梅花為 4 張時）
        - 否認 5 張高花（除非 11-15 且不夠開叫 1H/1S 的條件）

  - bid: "1H"
    id: "open-1h"
    meaning:
      description: "紅心開叫，五張以上"
      hand:
        hcp: { min: 11, max: 15 }
        hearts: { min: 5 }

  - bid: "1S"
    id: "open-1s"
    meaning:
      description: "黑桃開叫，五張以上"
      hand:
        hcp: { min: 11, max: 15 }
        spades: { min: 5 }

  - bid: "1NT"
    id: "open-1nt"
    meaning:
      description: "無王開叫，平均牌型"
      hand:
        hcp: { min: 13, max: 15 }   # 精準制用 13-15
        shape: { ref: "balanced" }
    conventions_applied:
      - ref: "conv-stayman"
      - ref: "conv-jacoby-transfer"
    responses:
      - bid: "2C"
        ref: "conv-stayman"          # 引用特約模組
      - bid: "2D"
        ref: "conv-jacoby-transfer"  # 引用轉換叫
      - bid: "2H"
        ref: "conv-jacoby-transfer"
      - bid: "2NT"
        meaning:
          description: "邀請 3NT"
          hand:
            hcp: { min: 11, max: 12 }
            shape: { ref: "balanced" }
      - bid: "3NT"
        meaning:
          description: "成局止叫"
          hand:
            hcp: { min: 13, max: 17 }
            shape: { ref: "balanced" }

  - bid: "2C"
    id: "open-2c"
    meaning:
      description: "梅花開叫，六張以上或五張強套"
      hand:
        hcp: { min: 11, max: 15 }
        clubs: { min: 5 }

  - bid: "2D"
    id: "open-2d"
    meaning:
      description: "精準制 2D 開叫"
      hand:
        hcp: { min: 11, max: 15 }
        conditions:
          - description: "短方塊三花色牌型 (4-4-1-4 或 4-4-0-5)"
            shape_constraint: "4-4-x-4"  # x = 0 或 1
            diamonds: { max: 1 }
      artificial: true
      alertable: true

  - bid: "2H"
    id: "open-2h"
    meaning:
      description: "弱二紅心開叫"
      hand:
        hcp: { min: 5, max: 10 }
        hearts: { min: 6, max: 6 }    # 恰好六張
      preemptive: true

  - bid: "2S"
    id: "open-2s"
    meaning:
      description: "弱二黑桃開叫"
      hand:
        hcp: { min: 5, max: 10 }
        spades: { min: 6, max: 6 }
      preemptive: true

  - bid: "2NT"
    id: "open-2nt"
    meaning:
      description: "無王開叫，平均牌型"
      hand:
        hcp: { min: 20, max: 21 }
        shape: { ref: "balanced" }

  # 三階及以上先制叫
  - bid: "3C"
    id: "open-3c"
    meaning:
      description: "先制開叫"
      hand:
        hcp: { min: 5, max: 10 }
        clubs: { min: 7 }
      preemptive: true

  # ... (3D, 3H, 3S, 3NT, 4C, 4D, 4H, 4S 類似)

# ========================================
# 防禦性叫牌
# ========================================
defensive:

  overcalls:
    simple:
      - level: 1
        meaning:
          description: "一階花色爭叫"
          hand:
            hcp: { min: 8, max: 16 }
            suit_length: { min: 5 }   # 爭叫花色至少五張
    jump:
      - levels_above: 1               # 跳叫爭叫
        meaning:
          description: "弱跳叫爭叫"
          hand:
            hcp: { min: 5, max: 10 }
            suit_length: { min: 6 }
          preemptive: true

  doubles:
    takeout:
      description: "技術性賭倍"
      conditions:
        - opponent_bid_level: { max: 3 }
          hand:
            hcp: { min: 12 }
            support_for_unbid_suits: true
    penalty:
      description: "懲罰性賭倍"
      conditions:
        - context: "搭檔已開叫或爭叫"
        - context: "高階叫牌"

  # NT 爭叫
  nt_overcalls:
    direct:
      bid: "1NT"
      meaning:
        description: "1NT 爭叫（等同 1NT 開叫）"
        hand:
          hcp: { min: 15, max: 18 }
          shape: { ref: "balanced" }
          stopper_in: opponent_suit    # 對手花色有擋張

# ========================================
# 競叫對策
# ========================================
competitive:

  after_opponent_overcall:
    negative_double:
      description: "負性賭倍"
      applies_through: "3S"            # 適用到對手爭叫 3S
      shows:
        unbid_major: { min: 4 }
        hcp: { min: 8 }

  after_opponent_double:
    redouble:
      description: "再賭倍顯示 10+ HCP"
      hand:
        hcp: { min: 10 }
    jordan_2nt:
      description: "對高花開叫被賭倍後，2NT 表示好的加叫"
      trigger:
        partner_opened: ["1H", "1S"]
        opponent: "X"
      hand:
        support_for_partner: { min: 4 }
        hcp: { min: 10 }

# ========================================
# 驗證規則 (供工具使用)
# ========================================
validation:
  rules:
    - id: "val-hcp-coverage"
      description: "每個花色開叫在其 HCP 範圍內不應有遺漏牌型"
      severity: warning

    - id: "val-no-overlap"
      description: "同一層級的叫品不應有 HCP 和牌型重疊"
      severity: error

    - id: "val-response-complete"
      description: "每個開叫應定義完整的回應體系"
      severity: warning

    - id: "val-convention-ref"
      description: "引用的特約模組必須在 conventions 區定義"
      severity: error

    - id: "val-alertable"
      description: "人工叫品必須標記 alertable: true"
      severity: warning
```

---

## 設計原則

### 1. 模組化 (Modularity)
特約（Convention）獨立定義，透過 `ref` 引用組合。社群可以共享特約模組，
不同制度引用相同的 Stayman、Blackwood 等。

### 2. 繼承性 (Inheritance)
制度可透過 `base` 欄位繼承另一個制度，只覆寫差異部分。
例如：「我的精準制」可繼承「標準精準制」，只改 1NT 範圍。

### 3. 可驗證性 (Verifiability)
`validation` 區塊定義檢查規則，工具可自動偵測：
- HCP 區間遺漏（某些牌力沒有對應的開叫）
- 牌型覆蓋不全（某些牌型不知道該開什麼）
- 叫品語義衝突（同一序列中兩個叫品條件重疊）

### 4. 漸進式定義 (Progressive Detail)
不需要一次定義完整制度。可以先定義開叫，再逐步補充回應、
再叫、競叫對策。工具會提示哪些部分尚未定義。

### 5. 多語系支援 (i18n)
`locale` 欄位支援多語系，description 可提供多語版本，
讓國際橋牌社群都能使用。

---

## 後續規劃

### Phase 1: Schema 穩定化
- [ ] 完善 JSON Schema 定義
- [ ] 建立更多制度範例（自然制、SAYC、Acol）
- [ ] 社群回饋收集

### Phase 2: 工具鏈
- [ ] YAML 驗證器（一致性檢查）
- [ ] 視覺化渲染器（叫牌樹 → SVG/HTML）
- [ ] 約定卡產生器（YAML → WBF 標準約定卡格式）

### Phase 3: AI 整合
- [ ] 制度知識庫載入器
- [ ] 模擬對練引擎
- [ ] 練習題自動產生器

### Phase 4: 社群平台
- [ ] Convention 模組市集
- [ ] 制度版本控制與 diff
- [ ] 線上編輯器
