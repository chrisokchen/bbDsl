# BBDSL - Bridge Bidding Description Specification Language
# 版本: 0.2.0-draft
# 修訂依據: 競品調查報告 (2026-02-26)

---

## 變更記錄 (Changelog)

### v0.2.0 vs v0.1.0

| 變更項目 | 調查來源 | 說明 |
|----------|----------|------|
| 新增 `seat` / `vulnerability` 一等公民 | BBOalert | 座位與身價影響叫牌意義 |
| 叫牌樹改為混合式（巢狀 + 路徑） | bidding-system-as-code | 解決深層巢狀縮排問題 |
| 新增對稱性語法糖 `foreach_suit` | bidding-system-as-code | Jacoby Transfer 等對稱序列只寫一次 |
| 新增 `opponent_context` 萬用字元 | BBOalert | 競叫時對手叫品的模式匹配 |
| Convention 支援版本與參數化 | BML COPY/PASTE | 同一特約的變體（如 regular vs puppet Stayman） |
| 新增 `export` 區塊 | 全部 | 定義輸出到 BBOalert/BML/Convention Card 的映射 |
| 強化 `hand` 約束模型 | 獨有優勢 | 新增牌套品質、擋張、控制力等語義約束 |
| 新增 `i18n` 多語系描述 | BBOalert Alias | description 支援多語版本 |
| 新增 `forcing` 語義層級 | 橋牌語義需求 | 區分 forcing/invitational/signoff 等 |
| 新增 `completeness` 元資料 | 漸進式設計 | 標示哪些部分已完成、哪些待補 |

---

## 設計目標（修訂版）

1. **通用性**：能描述任意叫牌制度
2. **教學友善**：支援視覺化呈現叫牌邏輯樹
3. **機器可驗證**：支援一致性檢查、遺漏偵測、衝突檢測
4. **AI 可讀**：作為 AI 對練的制度知識庫
5. **社群協作**：模組化設計，Convention 可獨立定義與組合
6. **🆕 互通性**：可匯出為 BBOalert / BML / WBF Convention Card 格式
7. **🆕 情境感知**：座位、身價、對手叫牌作為一等公民

---

## 核心概念模型（修訂版）

```
System (制度)
  ├── Metadata (元資料)
  │     ├── base (繼承)
  │     ├── locale / i18n (多語系)
  │     └── completeness (完成度)
  ├── Definitions (全域定義)
  │     ├── HandPatterns (牌型模式)
  │     ├── StrengthRanges (牌力區間)
  │     ├── SuitQualities (牌套品質)
  │     └── Variables (可參數化變數)
  ├── Conventions (特約模組庫)
  │     └── 每個 Convention 可獨立發布、版本化、參數化
  ├── Bidding (叫牌規則) ← 統一的叫牌樹
  │     ├── Openings (開叫)
  │     ├── Responses (回應)
  │     ├── Rebids (再叫)
  │     ├── Defensive (防禦叫牌)
  │     └── Competitive (競叫對策)
  ├── Contexts (情境修飾)
  │     ├── seat (座位條件)
  │     ├── vulnerability (身價條件)
  │     └── opponent_actions (對手行為)
  ├── Validation (驗證規則)
  └── Export (匯出設定)
        ├── bboalert
        ├── bml
        └── convention_card
```

---

## Schema 規格 (v0.2)

```yaml
bbdsl: "0.2"

# ========================================
# 制度元資料
# ========================================
system:
  name: "精準制 (Precision Club)"
  version: "2.0.0"
  authors:
    - name: "C.C. Wei"
    - name: "Chris"                    # 修改者
      role: "maintainer"
  description:
    zh-TW: "經典精準制，強梅花開叫"
    en: "Classic Precision Club, strong club opening"
  base: null                           # 可繼承其他制度 URI
  locale: "zh-TW"                      # 預設語系
  license: "CC-BY-SA-4.0"             # 社群共享授權

  # 🆕 完成度標示
  completeness:
    openings: complete
    responses_to_1c: complete
    responses_to_1d: partial
    responses_to_1h: draft
    responses_to_1s: draft
    responses_to_1nt: complete
    defensive: partial
    competitive: draft
    slam_bidding: todo

# ========================================
# 全域定義區
# ========================================
definitions:

  # --- 牌力評估方法 ---
  strength_methods:
    hcp:
      description:
        zh-TW: "大牌點 (A=4, K=3, Q=2, J=1)"
        en: "High Card Points (A=4, K=3, Q=2, J=1)"
      range: [0, 37]
    controls:
      description:
        zh-TW: "控制 (A=2, K=1)"
        en: "Controls (A=2, K=1)"
      range: [0, 12]
    losing_tricks:
      description:
        zh-TW: "失墩計算法"
        en: "Losing Trick Count"
      range: [0, 12]
    total_points:
      description:
        zh-TW: "總點力 (HCP + 分配點)"
        en: "Total Points (HCP + distribution)"
      range: [0, 40]

  # --- 牌型模式 (可重用) ---
  patterns:
    balanced:
      description:
        zh-TW: "平均牌型"
        en: "Balanced"
      shapes:
        - "4-3-3-3"
        - "4-4-3-2"
        - "5-3-3-2"

    semi_balanced:
      description:
        zh-TW: "半平均牌型"
        en: "Semi-balanced"
      shapes:
        - "5-4-2-2"
        - "6-3-2-2"

    any_single_suited:
      description:
        zh-TW: "單花色套"
        en: "Single-suited"
      constraints:
        longest_suit: { min: 6 }

    any_two_suited:
      description:
        zh-TW: "雙花色套"
        en: "Two-suited"
      constraints:
        longest_suit: { min: 5 }
        second_suit: { min: 4 }

  # 🆕 --- 牌套品質定義 ---
  suit_qualities:
    good:
      description:
        zh-TW: "好套：前三張大牌有兩張，或前五張有三張"
        en: "Good suit: 2 of top 3 honors, or 3 of top 5"
      top3_honors: { min: 2 }          # AKQ 中至少兩張
    strong:
      description:
        zh-TW: "強套：AKQ 中至少兩張且長度 6+"
        en: "Strong suit: 2+ of AKQ with 6+ length"
      top3_honors: { min: 2 }
      min_length: 6
    weak:
      description:
        zh-TW: "弱套：缺乏大牌"
        en: "Weak suit: lacking honors"
      top3_honors: { max: 0 }

  # 🆕 --- 花色群組 (語法糖用) ---
  suit_groups:
    majors: ["H", "S"]
    minors: ["C", "D"]
    reds: ["H", "D"]
    blacks: ["S", "C"]
    all: ["C", "D", "H", "S"]

# ========================================
# 🆕 情境定義 (Context)
# ========================================
# 座位、身價、對手行為作為一等公民
# 任何叫牌節點都可附加 context 條件

contexts:
  # 預設情境（不指定時使用）
  default:
    seat: any                          # 1st|2nd|3rd|4th|any
    vulnerability: any                 # none|us|them|both|any
    opponent_action: none              # none|pass|bid|double|any

  # 命名情境（可在叫牌節點中引用）
  third_seat_nv:
    seat: 3rd
    vulnerability: none

  third_seat_vul:
    seat: 3rd
    vulnerability: us

  passed_hand:
    seat: [3rd, 4th]                   # 陣列表示「任一」
    precondition: "partner_passed"     # 搭檔已 pass

# ========================================
# 特約模組 (Convention Modules) - 強化版
# ========================================
conventions:

  # --- Stayman 家族 ---
  stayman:
    id: "conv-stayman"
    name: "Stayman"
    version: "standard-v1"
    category: "notrump_response"       # 🆕 分類
    description:
      zh-TW: "對 NT 開叫後問四張高花"
      en: "Asks for 4-card major after NT opening"

    # 🆕 參數化：讓引用者可以覆寫預設值
    parameters:
      nt_bid: "1NT"                    # 預設觸發叫品
      response_bid: "2C"              # 預設 Stayman 叫品
      garbage_stayman: true            # 是否允許垃圾 Stayman

    trigger:
      after: ["${nt_bid}"]
      bid: "${response_bid}"

    requires: []
    conflicts_with: ["conv-puppet-stayman"]  # 🆕 互斥約定

    # 🆕 使用者需求
    responder_hand:
      hcp: { min: 0 }                 # garbage stayman 時可以 0
      conditions:
        - any_of:
            - { hearts: { min: 4 } }
            - { spades: { min: 4 } }
            # garbage stayman: 4-4-4-1 or 4-4-5-0 弱牌
            - when: "${garbage_stayman}"
              shape_includes: ["4-4-4-1", "4-4-5-0"]
              hcp: { max: 7 }

    responses:
      - bid: "2D"
        by: opener
        meaning:
          description:
            zh-TW: "否認持有四張高花"
            en: "Denies 4-card major"
          hand:
            hearts: { max: 3 }
            spades: { max: 3 }
        continuations:
          - bid: "Pass"
            by: responder
            context: { ref: "garbage_stayman_pass" }
            meaning:
              description:
                zh-TW: "垃圾 Stayman 逃跑"
                en: "Garbage Stayman escape"

          - bid: "2H"
            by: responder
            meaning:
              description:
                zh-TW: "邀請，五張紅心"
                en: "Invitational, 5 hearts"
              hand:
                hearts: { min: 5 }
                hcp: { min: 8, max: 9 }
              forcing: none

          - bid: "2S"
            by: responder
            meaning:
              description:
                zh-TW: "邀請，五張黑桃"
                en: "Invitational, 5 spades"
              hand:
                spades: { min: 5 }
                hcp: { min: 8, max: 9 }
              forcing: none

          - bid: "2NT"
            by: responder
            meaning:
              description:
                zh-TW: "邀請 3NT，無四張高花"
                en: "Invitational to 3NT, no 4-card major"
              hand:
                hcp: { min: 8, max: 9 }
                hearts: { max: 3 }
                spades: { max: 3 }
              forcing: none

          - bid: "3NT"
            by: responder
            meaning:
              description:
                zh-TW: "止叫 3NT"
                en: "Signoff 3NT"
              hand:
                hcp: { min: 10 }
                hearts: { max: 3 }
                spades: { max: 3 }
              forcing: signoff

      - bid: "2H"
        by: opener
        meaning:
          description:
            zh-TW: "四張紅心（可能也有四張黑桃）"
            en: "4 hearts (may also have 4 spades)"
          hand:
            hearts: { min: 4 }
        continuations:
          - bid: "2NT"
            by: responder
            meaning:
              description:
                zh-TW: "邀請，不配合紅心"
                en: "Invitational, no heart fit"
              hand:
                hearts: { max: 3 }
                hcp: { min: 8, max: 9 }

          - bid: "3H"
            by: responder
            meaning:
              description:
                zh-TW: "邀請，配合紅心"
                en: "Invitational with heart fit"
              hand:
                hearts: { min: 4 }
                hcp: { min: 8, max: 9 }

          - bid: "3NT"
            by: responder
            meaning:
              description:
                zh-TW: "止叫，不配合紅心"
                en: "Signoff, no heart fit"
              hand:
                hearts: { max: 3 }
                hcp: { min: 10 }

          - bid: "4H"
            by: responder
            meaning:
              description:
                zh-TW: "成局，配合紅心"
                en: "Game, heart fit"
              hand:
                hearts: { min: 4 }
                hcp: { min: 10 }

          # 🆕 Smolen: 如果有 5-4 高花且迫叫
          - bid: "3S"
            by: responder
            meaning:
              description:
                zh-TW: "Smolen：五張黑桃四張紅心，迫叫成局"
                en: "Smolen: 5 spades, 4 hearts, game force"
              hand:
                spades: { min: 5 }
                hearts: { min: 4 }
                hcp: { min: 10 }
              forcing: game

      - bid: "2S"
        by: opener
        meaning:
          description:
            zh-TW: "四張黑桃，非四張紅心"
            en: "4 spades, denies 4 hearts"
          hand:
            spades: { min: 4 }
            hearts: { max: 3 }

  # --- Jacoby Transfer ---
  # 🆕 使用 foreach_suit 語法糖展示對稱性
  jacoby_transfer:
    id: "conv-jacoby-transfer"
    name:
      zh-TW: "乔乗轉換叫"
      en: "Jacoby Transfer"
    version: "standard-v1"
    category: "notrump_response"

    parameters:
      nt_bid: "1NT"

    trigger:
      after: ["${nt_bid}"]

    # 🆕 foreach_suit: 對稱性定義
    # 下面的定義會自動展開為 2D→H 和 2H→S 兩組
    foreach_suit:
      variable: M                        # 迭代變數名
      over: majors                       # 引用 suit_groups.majors
      transfer_bid: "2${M.transfer_from}" # 2D for H, 2H for S
      target_suit: "${M}"

    bids:
      - bid: "${transfer_bid}"
        by: responder
        meaning:
          description:
            zh-TW: "轉換至${M.zh-TW}，五張以上"
            en: "Transfer to ${M}, 5+ cards"
          hand:
            "${M}": { min: 5 }
          artificial: true
          alertable: true               # ACBL: announced, not alerted

        continuations:
          - bid: "2${M}"
            by: opener
            meaning:
              description:
                zh-TW: "完成轉換"
                en: "Complete transfer"
            continuations:
              - bid: "Pass"
                by: responder
                meaning:
                  description:
                    zh-TW: "止叫"
                    en: "Signoff"
                  hand:
                    hcp: { max: 7 }
                  forcing: signoff

              - bid: "2NT"
                by: responder
                meaning:
                  description:
                    zh-TW: "邀請，可選 3NT 或 3${M}"
                    en: "Invitational, choice of 3NT or 3${M}"
                  hand:
                    "${M}": { exactly: 5 }
                    hcp: { min: 8, max: 9 }
                  forcing: invitational

              - bid: "3${M}"
                by: responder
                meaning:
                  description:
                    zh-TW: "邀請，六張以上${M.zh-TW}"
                    en: "Invitational, 6+ ${M}"
                  hand:
                    "${M}": { min: 6 }
                    hcp: { min: 8, max: 9 }
                  forcing: invitational

              - bid: "3NT"
                by: responder
                meaning:
                  description:
                    zh-TW: "迫叫成局，恰好五張${M.zh-TW}，讓開叫者選"
                    en: "Game force, exactly 5 ${M}, choice of games"
                  hand:
                    "${M}": { exactly: 5 }
                    hcp: { min: 10 }
                  forcing: game

              - bid: "4${M}"
                by: responder
                meaning:
                  description:
                    zh-TW: "成局止叫，六張以上"
                    en: "Game signoff, 6+"
                  hand:
                    "${M}": { min: 6 }
                    hcp: { min: 10, max: 14 }
                  forcing: signoff

          # 🆕 Super-accept
          - bid: "3${M}"
            by: opener
            meaning:
              description:
                zh-TW: "超級接受：四張配合且牌力上限"
                en: "Super-accept: 4-card fit, maximum"
              hand:
                "${M}": { min: 4 }
                hcp: { min: 16, max: 17 }  # 相對於 15-17 NT

  # 🆕 --- 展示 Convention 互斥與依賴 ---
  puppet_stayman:
    id: "conv-puppet-stayman"
    name: "Puppet Stayman"
    version: "v1"
    category: "notrump_response"
    conflicts_with: ["conv-stayman"]     # 與普通 Stayman 互斥
    trigger:
      after: ["2NT"]
      bid: "3C"
    responses:
      - bid: "3D"
        by: opener
        meaning:
          description:
            zh-TW: "至少一個四張高花（無五張）"
            en: "At least one 4-card major (no 5-card)"
          hand:
            conditions:
              - any_of:
                  - { hearts: { min: 4, max: 4 } }
                  - { spades: { min: 4, max: 4 } }
      - bid: "3H"
        by: opener
        meaning:
          description:
            zh-TW: "五張紅心"
            en: "5 hearts"
          hand:
            hearts: { min: 5 }
      - bid: "3S"
        by: opener
        meaning:
          description:
            zh-TW: "五張黑桃"
            en: "5 spades"
          hand:
            spades: { min: 5 }
      - bid: "3NT"
        by: opener
        meaning:
          description:
            zh-TW: "無四張以上高花"
            en: "No 4+ card major"
          hand:
            hearts: { max: 3 }
            spades: { max: 3 }

# ========================================
# 開叫定義
# ========================================
openings:

  - bid: "Pass"
    id: "open-pass"
    meaning:
      description:
        zh-TW: "不開叫"
        en: "No opening"
      hand:
        hcp: { max: 10 }               # 精準制中低於 11 不開叫
      notes:
        zh-TW: "11-15 時若無合適開叫也可能 Pass（極少見）"

  - bid: "1C"
    id: "open-1c"
    meaning:
      description:
        zh-TW: "強梅花開叫"
        en: "Strong club opening"
      hand:
        hcp: { min: 16 }
        shape: any
      artificial: true
      alertable: true
      forcing: one_round                # 🆕 forcing 語義

    # 🆕 情境覆寫
    context_overrides:
      - context:
          seat: 3rd
          vulnerability: none
        meaning:
          hand:
            hcp: { min: 15 }            # 第三家 NV 可以稍微放寬
          notes:
            zh-TW: "第三家非身價可降至 15 HCP"

    responses:
      # 🆕 對手行為分支
      - when_opponent: pass             # 對手 Pass 時的回應
        bids:
          - bid: "1D"
            id: "resp-1c-1d"
            meaning:
              description:
                zh-TW: "否認叫（消極回應）"
                en: "Negative response"
              hand:
                hcp: { min: 0, max: 7 }
              artificial: true
              alertable: true
              forcing: one_round

            continuations:
              - bid: "1H"
                by: opener
                meaning:
                  description:
                    zh-TW: "四張以上紅心，16+ HCP"
                    en: "4+ hearts, 16+ HCP"
                  hand:
                    hearts: { min: 4 }
                  forcing: one_round

              - bid: "1S"
                by: opener
                meaning:
                  description:
                    zh-TW: "四張以上黑桃，16+ HCP"
                    en: "4+ spades, 16+ HCP"
                  hand:
                    spades: { min: 4 }
                  forcing: one_round

              - bid: "1NT"
                by: opener
                meaning:
                  description:
                    zh-TW: "平均牌型，16-18 HCP"
                    en: "Balanced, 16-18 HCP"
                  hand:
                    hcp: { min: 16, max: 18 }
                    shape: { ref: "balanced" }
                  forcing: none

              - bid: "2C"
                by: opener
                meaning:
                  description:
                    zh-TW: "五張以上梅花，16+ HCP"
                    en: "5+ clubs, 16+ HCP"
                  hand:
                    clubs: { min: 5 }
                  forcing: one_round

              - bid: "2D"
                by: opener
                meaning:
                  description:
                    zh-TW: "五張以上方塊，16+ HCP"
                    en: "5+ diamonds, 16+ HCP"
                  hand:
                    diamonds: { min: 5 }
                  forcing: one_round

              - bid: "2NT"
                by: opener
                meaning:
                  description:
                    zh-TW: "平均牌型，22-23 HCP"
                    en: "Balanced, 22-23 HCP"
                  hand:
                    hcp: { min: 22, max: 23 }
                    shape: { ref: "balanced" }
                  forcing: game

              - bid: "3NT"
                by: opener
                meaning:
                  description:
                    zh-TW: "平均牌型，24+ HCP"
                    en: "Balanced, 24+ HCP"
                  hand:
                    hcp: { min: 24 }
                    shape: { ref: "balanced" }
                  forcing: signoff

          - bid: "1H"
            id: "resp-1c-1h"
            meaning:
              description:
                zh-TW: "8+ HCP，五張以上紅心"
                en: "8+ HCP, 5+ hearts"
              hand:
                hcp: { min: 8 }
                hearts: { min: 5 }
              forcing: game

          - bid: "1S"
            id: "resp-1c-1s"
            meaning:
              description:
                zh-TW: "8+ HCP，五張以上黑桃"
                en: "8+ HCP, 5+ spades"
              hand:
                hcp: { min: 8 }
                spades: { min: 5 }
              forcing: game

          - bid: "1NT"
            id: "resp-1c-1nt"
            meaning:
              description:
                zh-TW: "8-13 HCP，平均牌型，無五張高花"
                en: "8-13 HCP, balanced, no 5-card major"
              hand:
                hcp: { min: 8, max: 13 }
                shape: { ref: "balanced" }
                hearts: { max: 4 }
                spades: { max: 4 }
              forcing: one_round

          - bid: "2C"
            id: "resp-1c-2c"
            meaning:
              description:
                zh-TW: "8+ HCP，五張以上梅花"
                en: "8+ HCP, 5+ clubs"
              hand:
                hcp: { min: 8 }
                clubs: { min: 5 }
              forcing: game

          - bid: "2D"
            id: "resp-1c-2d"
            meaning:
              description:
                zh-TW: "8+ HCP，五張以上方塊"
                en: "8+ HCP, 5+ diamonds"
              hand:
                hcp: { min: 8 }
                diamonds: { min: 5 }
              forcing: game

          - bid: "2NT"
            id: "resp-1c-2nt"
            meaning:
              description:
                zh-TW: "14+ HCP，平均牌型"
                en: "14+ HCP, balanced"
              hand:
                hcp: { min: 14 }
                shape: { ref: "balanced" }
              forcing: game

      # 🆕 對手爭叫時的回應
      - when_opponent: double            # 對手賭倍 1C
        bids:
          - bid: "XX"
            meaning:
              description:
                zh-TW: "10+ HCP，懲罰意圖"
                en: "10+ HCP, penalty oriented"
              hand:
                hcp: { min: 10 }
          - bid: "Pass"
            meaning:
              description:
                zh-TW: "0-4 HCP"
                en: "0-4 HCP"
              hand:
                hcp: { max: 4 }
          - bid: "1D"
            meaning:
              description:
                zh-TW: "5-9 HCP（改為顯示值）"
                en: "5-9 HCP (shows values)"
              hand:
                hcp: { min: 5, max: 9 }
              artificial: true

      - when_opponent: bid               # 對手花色爭叫
        # 🆕 萬用字元：opponent_bid 是變數
        bids:
          - bid: "X"
            meaning:
              description:
                zh-TW: "負性賭倍，8+ HCP"
                en: "Negative double, 8+ HCP"
              hand:
                hcp: { min: 8 }
          - bid: "Pass"
            meaning:
              description:
                zh-TW: "0-7 HCP 或陷阱 Pass"
                en: "0-7 HCP or trap pass"
              hand:
                hcp: { max: 7 }
          - bid: "cue_bid"               # 🆕 語義叫品（叫對手花色）
            meaning:
              description:
                zh-TW: "10+ HCP，迫叫"
                en: "10+ HCP, forcing"
              hand:
                hcp: { min: 10 }
              forcing: one_round

  - bid: "1D"
    id: "open-1d"
    meaning:
      description:
        zh-TW: "方塊開叫，可能短方塊"
        en: "Diamond opening, may be short"
      hand:
        hcp: { min: 11, max: 15 }
        diamonds: { min: 2 }             # 最少可能只有兩張
        spades: { max: 4 }              # 否認五張高花
        hearts: { max: 4 }
      notes:
        zh-TW: |
          精準制中 1D 開叫較為複雜：
          - 11-15 HCP
          - 可能只有 2 張方塊（4=4=3=2 型，梅花 4 張時）
          - 否認 5 張高花
        en: |
          Precision 1D is complex:
          - 11-15 HCP
          - May have only 2 diamonds (4=4=3=2 with 4 clubs)
          - Denies 5-card major

  # 🆕 使用 foreach_suit 展示 1H/1S 的對稱性
  - foreach_suit:
      variable: M
      over: majors
    bid: "1${M}"
    id: "open-1${M.lower}"
    meaning:
      description:
        zh-TW: "五張以上${M.zh-TW}開叫"
        en: "5+ ${M} opening"
      hand:
        hcp: { min: 11, max: 15 }
        "${M}": { min: 5 }
    responses:
      - when_opponent: pass
        bids:
          - bid: "1NT"
            meaning:
              description:
                zh-TW: "6-9 HCP，否認支持"
                en: "6-9 HCP, denies support"
              hand:
                hcp: { min: 6, max: 9 }
                "${M}": { max: 2 }
              forcing: none

          - bid: "2${M}"
            meaning:
              description:
                zh-TW: "簡單加叫，6-9 HCP，三張以上支持"
                en: "Simple raise, 6-9 HCP, 3+ support"
              hand:
                hcp: { min: 6, max: 9 }
                "${M}": { min: 3 }
              forcing: none

          - bid: "3${M}"
            meaning:
              description:
                zh-TW: "限制性加叫，10-12 HCP，四張以上支持"
                en: "Limit raise, 10-12 HCP, 4+ support"
              hand:
                hcp: { min: 10, max: 12 }
                "${M}": { min: 4 }
              forcing: invitational

          - bid: "4${M}"
            meaning:
              description:
                zh-TW: "先制性成局，好支持但牌力有限"
                en: "Preemptive game, good support but limited"
              hand:
                "${M}": { min: 5 }
                hcp: { max: 9 }
              forcing: signoff
              preemptive: true

  - bid: "1NT"
    id: "open-1nt"
    meaning:
      description:
        zh-TW: "無王開叫，平均牌型"
        en: "Notrump opening, balanced"
      hand:
        hcp: { min: 13, max: 15 }
        shape: { ref: "balanced" }

    # 🆕 情境覆寫：第三/四家可能拓寬
    context_overrides:
      - context:
          seat: [3rd, 4th]
        meaning:
          hand:
            hcp: { min: 11, max: 15 }
          notes:
            zh-TW: "第三/四家可降至 11 HCP"

    # Convention 引用
    conventions_applied:
      - ref: "conv-stayman"
        parameters:
          nt_bid: "1NT"
          response_bid: "2C"
          garbage_stayman: true
      - ref: "conv-jacoby-transfer"
        parameters:
          nt_bid: "1NT"

    responses:
      - when_opponent: pass
        bids:
          - bid: "2C"
            ref: "conv-stayman"
          - bid: "2D"
            ref: "conv-jacoby-transfer"
          - bid: "2H"
            ref: "conv-jacoby-transfer"
          - bid: "2S"
            meaning:
              description:
                zh-TW: "低花轉換叫（如有約定）"
                en: "Minor suit transfer (if agreed)"
              alertable: true
              artificial: true
          - bid: "2NT"
            meaning:
              description:
                zh-TW: "邀請 3NT"
                en: "Invitational to 3NT"
              hand:
                hcp: { min: 11, max: 12 }
                shape: { ref: "balanced" }
              forcing: invitational
          - bid: "3NT"
            meaning:
              description:
                zh-TW: "成局止叫"
                en: "Game signoff"
              hand:
                hcp: { min: 13, max: 17 }
                shape: { ref: "balanced" }
              forcing: signoff
          - bid: "4NT"
            meaning:
              description:
                zh-TW: "量化邀請滿貫"
                en: "Quantitative slam invite"
              hand:
                hcp: { min: 18, max: 19 }
                shape: { ref: "balanced" }
              forcing: invitational

      # 🆕 對手爭叫時
      - when_opponent: double
        bids:
          - bid: "XX"
            meaning:
              description:
                zh-TW: "懲罰導向，10+ HCP"
                en: "Penalty oriented, 10+ HCP"
              hand:
                hcp: { min: 10 }
          - bid: "systems_on"            # 🆕 「制度照常」語義標記
            meaning:
              description:
                zh-TW: "繼續使用 Stayman / Transfer"
                en: "Systems on: Stayman / Transfer still apply"

      - when_opponent: bid
        convention_ref: "conv-lebensohl"  # 🆕 整套引用競叫約定

  - bid: "2C"
    id: "open-2c"
    meaning:
      description:
        zh-TW: "自然梅花開叫，11-15 HCP，五張以上梅花"
        en: "Natural club opening, 11-15 HCP, 5+ clubs"
      hand:
        hcp: { min: 11, max: 15 }
        clubs: { min: 5 }

  - bid: "2D"
    id: "open-2d"
    meaning:
      description:
        zh-TW: "精準 2D：短方塊三花色"
        en: "Precision 2D: short diamond, 3-suited"
      hand:
        hcp: { min: 11, max: 15 }
        diamonds: { max: 1 }
        hearts: { min: 4 }
        spades: { min: 4 }
        clubs: { min: 4 }
      artificial: true
      alertable: true

  # 弱二開叫 (使用 foreach_suit)
  - foreach_suit:
      variable: M
      over: majors
    bid: "2${M}"
    id: "open-2${M.lower}-weak"
    meaning:
      description:
        zh-TW: "弱二${M.zh-TW}開叫"
        en: "Weak two ${M}"
      hand:
        hcp: { min: 5, max: 10 }
        "${M}": { min: 6, max: 6 }
        suit_quality:
          "${M}": { ref: "good" }        # 🆕 引用牌套品質定義
      preemptive: true

    # 🆕 弱二的座位/身價差異
    context_overrides:
      - context:
          seat: 1st
          vulnerability: us
        meaning:
          hand:
            hcp: { min: 6, max: 10 }     # 身價時要求更高
            suit_quality:
              "${M}": { ref: "strong" }
          notes:
            zh-TW: "有身價時花色品質要求更高"

      - context:
          seat: 3rd
        meaning:
          hand:
            hcp: { min: 3, max: 10 }     # 第三家可以更弱
            "${M}": { min: 5 }            # 甚至五張也行
          notes:
            zh-TW: "第三家可放寬至五張 3 HCP"

  - bid: "2NT"
    id: "open-2nt"
    meaning:
      description:
        zh-TW: "強無王開叫"
        en: "Strong notrump opening"
      hand:
        hcp: { min: 20, max: 21 }
        shape: { ref: "balanced" }
    conventions_applied:
      - ref: "conv-puppet-stayman"
      - ref: "conv-jacoby-transfer"
        parameters:
          nt_bid: "2NT"

  # 三階先制叫 (使用 foreach_suit)
  - foreach_suit:
      variable: s
      over: all
    bid: "3${s}"
    id: "open-3${s.lower}"
    meaning:
      description:
        zh-TW: "先制開叫，七張以上${s.zh-TW}"
        en: "Preemptive opening, 7+ ${s}"
      hand:
        hcp: { min: 5, max: 10 }
        "${s}": { min: 7 }
      preemptive: true

# ========================================
# 🆕 防禦性叫牌 (統一結構)
# ========================================
defensive:

  # 🆕 用 when_opponent 統一表達觸發條件
  - when_opponent_opens: "1_suit"        # 對手開叫任何一階花色
    actions:
      simple_overcall:
        bid: "suit_at_cheapest_level"
        meaning:
          description:
            zh-TW: "一階花色爭叫"
            en: "Simple overcall"
          hand:
            hcp: { min: 8, max: 16 }
            bid_suit: { min: 5 }         # 爭叫花色至少五張

      jump_overcall:
        bid: "suit_jump"
        meaning:
          description:
            zh-TW: "弱跳叫爭叫"
            en: "Weak jump overcall"
          hand:
            hcp: { min: 5, max: 10 }
            bid_suit: { min: 6 }
          preemptive: true

      nt_overcall:
        bid: "1NT"
        meaning:
          description:
            zh-TW: "1NT 爭叫"
            en: "1NT overcall"
          hand:
            hcp: { min: 15, max: 18 }
            shape: { ref: "balanced" }
            stopper_in: opponent_suit
        conventions_applied:
          - ref: "conv-stayman"
            parameters: { nt_bid: "1NT" }
          - ref: "conv-jacoby-transfer"
            parameters: { nt_bid: "1NT" }

      takeout_double:
        bid: "X"
        meaning:
          description:
            zh-TW: "技術性賭倍"
            en: "Takeout double"
          hand:
            hcp: { min: 12 }
            support_for_unbid_suits: true
            # 或 17+ 任何牌型
            conditions:
              - any_of:
                  - support_for_unbid_suits: true
                    hcp: { min: 12 }
                  - hcp: { min: 17 }

  - when_opponent_opens: "1NT"
    # 🆕 可插入任何 defense convention
    convention_ref: "conv-dont"          # 例如 D.O.N.T. 防禦

# ========================================
# 🆕 forcing 語義枚舉
# ========================================
# forcing 的可能值及語義：
#   signoff:       止叫，搭檔應 Pass
#   none:          不迫叫，搭檔可 Pass
#   invitational:  邀請性，搭檔可 Pass 或接受
#   one_round:     一輪迫叫，搭檔至少再叫一次
#   game:          迫叫成局，不到成局不停
#   slam:          迫叫滿貫（罕見）

# ========================================
# 驗證規則 (強化版)
# ========================================
validation:
  rules:
    - id: "val-hcp-coverage"
      description:
        zh-TW: "開叫的 HCP 區間應完整覆蓋 0-37"
        en: "Opening HCP ranges should cover 0-37"
      severity: warning
      scope: openings

    - id: "val-no-overlap"
      description:
        zh-TW: "同一層級的叫品不應有 HCP+牌型條件重疊"
        en: "Same-level bids should not have overlapping HCP+shape"
      severity: error
      scope: all

    - id: "val-response-complete"
      description:
        zh-TW: "每個開叫應定義回應體系"
        en: "Every opening should have defined responses"
      severity: warning
      scope: openings

    - id: "val-convention-ref"
      description:
        zh-TW: "引用的特約模組必須存在"
        en: "Referenced conventions must exist"
      severity: error
      scope: all

    - id: "val-alertable"
      description:
        zh-TW: "人工叫品必須標記 alertable: true"
        en: "Artificial bids must be marked alertable"
      severity: warning
      scope: all

    - id: "val-forcing-consistency"
      description:
        zh-TW: "forcing: game 序列中不應出現非迫叫的後續叫品"
        en: "Game-forcing sequences should not have non-forcing continuations"
      severity: error
      scope: all

    - id: "val-convention-conflicts"
      description:
        zh-TW: "互斥的特約不應同時被引用"
        en: "Conflicting conventions should not be applied together"
      severity: error
      scope: conventions

    # 🆕 新增的驗證規則
    - id: "val-seat-vulnerability"
      description:
        zh-TW: "context_overrides 中的座位/身價組合不應衝突"
        en: "Seat/vulnerability overrides should not conflict"
      severity: error

    - id: "val-foreach-expansion"
      description:
        zh-TW: "foreach_suit 展開後不應產生叫品衝突"
        en: "foreach_suit expansion should not create bid conflicts"
      severity: error

# ========================================
# 🆕 匯出設定
# ========================================
export:

  bboalert:
    enabled: true
    # BBOalert 匯出設定
    format_version: "2.0"
    include_comments: true
    seat_dependent_openings: true
    # 自動產生 BBOalert 格式的叫牌序列→說明映射

  bml:
    enabled: true
    # BML 匯出設定
    output_format: html                  # html | latex | both
    include_suit_symbols: true

  convention_card:
    enabled: true
    format: "wbf"                        # wbf | acbl
    # 自動填入約定卡的對應欄位
```

---

## 設計原則（修訂版）

### 1. 模組化 (Modularity)
Convention 獨立定義，支援版本化、參數化、互斥/依賴宣告。
社群可以共享 Convention 模組，不同制度引用相同的 Stayman、Blackwood 等。

### 2. 繼承性 (Inheritance)
制度可透過 `base` 欄位繼承另一個制度，只覆寫差異部分。
`context_overrides` 讓座位/身價的變異也以差異化方式表達。

### 3. 可驗證性 (Verifiability)
validation rules 強化為 10 條，涵蓋：HCP 覆蓋、牌型重疊、forcing 一致性、
Convention 衝突、foreach 展開衝突等。

### 4. 情境感知 (Context-Awareness) 🆕
座位、身價、對手行為是一等公民，不是事後補丁。
`context_overrides` 允許在任何叫牌節點上附加情境條件。

### 5. 對稱性語法糖 (Symmetry Sugar) 🆕
`foreach_suit` 讓 Jacoby Transfer、弱二開叫等對稱序列只寫一次。
展開後的結果可被驗證器檢查。

### 6. 互通性 (Interoperability) 🆕
`export` 區塊定義到 BBOalert / BML / Convention Card 的映射。
寫一份 BBDSL，產生多種輸出。

### 7. 漸進式定義 (Progressive Detail)
`completeness` 元資料明確標示每個部分的完成狀態。
工具可提示哪些部分尚未定義，並計算整體完成度。

### 8. 多語系 (i18n) 🆕
所有 description 欄位支援多語版本。
預設語系由 `locale` 指定，匯出時可選擇語系。

---

## 後續規劃（修訂版）

### Phase 1: Schema 穩定化 (目前)
- [ ] 完善 JSON Schema 定義（配合 v0.2）
- [ ] 建立三個完整制度範例：精準制、SAYC、2/1 GF
- [ ] 定義 foreach_suit 的展開規則
- [ ] 社群回饋收集

### Phase 2: 核心工具鏈
- [ ] YAML 驗證器（實作 10 條 validation rules）
- [ ] foreach_suit 展開器
- [ ] BBOalert 匯出器（立即可用於 BBO 線上對打）
- [ ] BML 匯出器（產生可讀文件）

### Phase 3: 視覺化與教學
- [ ] 互動式 HTML Viewer（參考 bidding-system-as-code 的 UI）
  - 摺疊展開
  - 叫牌方顏色標示
  - hover 顯示完整序列 + 語義
  - 情境切換器（座位/身價）
- [ ] 約定卡產生器（WBF / ACBL 格式）
- [ ] 叫牌樹 SVG 圖表產生器

### Phase 4: AI 整合
- [ ] BBDSL → AI Knowledge Base 載入器
- [ ] 模擬對練引擎（給定手牌，按制度判斷最佳叫品）
- [ ] 練習題自動產生器
- [ ] 制度比較器（兩個制度對同一手牌的叫牌差異）

### Phase 5: 社群平台
- [ ] Convention 模組登錄（registry）
- [ ] 制度版本控制與 diff
- [ ] 線上 BBDSL 編輯器（YAML 編輯 + 即時預覽）
- [ ] 社群評分與推薦
