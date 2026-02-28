# BBDSL & BCC 系統架構白皮書
**下一代橋牌人工智慧與不完全資訊賽局的開源通訊協定**

> **版本:** 0.1.0-draft | **發布日期:** 2026-02
> **領域:** 人工智慧 (AI)、賽局理論 (Game Theory)、橋牌 (Contract Bridge)

---

## 摘要 (Abstract)

傳統的電腦橋牌 AI（如 GIB, WBridge5）在「雙明手（Double-Dummy）」分析上已臻完美，但在面對真實的「不完全資訊（Imperfect Information）」狀態時，往往表現得像是一台死背規則的機器。它們缺乏人類頂尖國手的核心技能：**「直覺（模糊邊界）」**與**「情報戰（戰術隱瞞與欺敵）」**。

本白皮書提出了一個雙層式的全新橋牌 AI 架構：
1. [**BBDSL (Bridge Bidding Description Specification Language)**](./README-bbDsl.md)：一套基於 YAML、為機器學習而生的橋牌制度描述語言，賦予規則「模糊邊界」與「戰術彈性」。
2. [**BCC (Bridge Communication Calculus)**](./README-bcc.md)：一套基於「貝氏機率微積分」與「夏農資訊熵」的賽局推理引擎，讓 AI 透過計算「資訊洩漏的代價」，自動湧現出戰術隱瞞與假信號的智慧。

這不僅是橋牌 AI 的下一個里程碑，更是探索**受限通道通訊 (Restricted Channel Communication)** 與 **多智能體強化學習 (MARL)** 的絕佳開源沙盒。

---

## 1. 痛點與背景 (Background)

### 1.1 現有橋牌 DSL 的極限
目前開源界主流的橋牌標記語言（如 BML 或 BBO BSS）主要為「人類排版」或「線上 Alert 系統」設計。它們是純粹的布林邏輯（Boolean Logic）：
*   例如：`1NT = 15-17 HCP, Balanced`。
*   **AI 的困境**：遇到 1NT 開叫時，傳統 AI 會將 14 點的可能世界機率直接砍成 `0.0`。一旦人類對手拿 14 點好牌「升級開叫」，AI 的算牌引擎就會崩潰（System Crash）。

### 1.2 現有 AI 的「誠實詛咒」
現有 AI 依賴啟發式規則（Heuristic Rules）加上蒙地卡羅模擬。當 AI 拿到 4 張堅固黑桃時，規則會強制它叫出黑桃。AI 不懂：**這聲叫牌雖然幫助了搭檔，但也同時向莊家洩漏了致命的情報，導致莊家完美避開飛牌盲點。**

---

## 2. BBDSL：具備 AI 語義的制度描述語言

**BBDSL** 是整個系統的「先驗知識庫」。它不僅定義了叫牌的點力與牌型，更獨創性地引入了 `ai_meta`（AI 元資料）區塊，讓冰冷的規則具備了機率彈性。

### 2.1 核心特性
*   **模組化 (Modularity)**：特約（Conventions，如 Stayman）獨立定義，可跨制度引用。
*   **模糊邊界 (Tolerances)**：定義容錯率，允許 AI 在推演時保留邊界情況的長尾機率。
*   **資訊意圖 (Intent)**：標記該叫品是「建設性 (Constructive)」、「破壞性 (Destructive)」還是「詢問 (Interrogative)」。

### 2.2 YAML 語法範例
```yaml
  - bid: "1NT"
    id: "open-1nt"
    meaning:
      description: "無王開叫，15-17點，平均牌型"
      hand:
        hcp: { min: 15, max: 17 }
        shape: { ref: "balanced" }
    # ====== AI 擴充區塊 ======
    ai_meta:
      intent: "constructive"
      tactical_flexibility: "strict"
      tolerances:                      # 定義模糊邊界
        hcp: 
          margin: 1                    # 允許 14 或 18 點的降/升級叫
          distribution: "gaussian"
      information_profile:
        leakage_risk: "critical"       # 洩漏風險：極高
      psych_probability: 0.01          # 允許 1% 的極端心理叫機率
```

---

## 3. BCC：橋牌通訊微積分 (The Logic Engine)

如果 BBDSL 是字典，那麼 **BCC (Bridge Communication Calculus)** 就是大腦。它將叫牌與防禦出牌視為在受限通道中發射的「信號（Signals）」。

### 3.1 貝氏大腦與粒子濾波 (Bayesian Filter)
BCC 不使用窮舉法（面對 $52!$ 的狀態空間是不可能的）。BCC 引擎在內部維護了上萬個「可能世界（Particles）」。當觀察到任何叫牌或出牌 $c$ 時，根據 BBDSL 的定義，計算貝氏後驗機率：

$$ P_{t+1}(w \mid c) = \frac{\mathcal{L}(c \mid w, \Gamma) \cdot P_t(w)}{\sum_{w' \in W} \mathcal{L}(c \mid w', \Gamma) \cdot P_t(w')} $$

這使得 BCC 能像人類大師一樣「削蘋果」——隨著叫牌進行，機率分佈會逐漸坍縮，精準鎖定對手的牌型，同時**保留對手騙人的雜訊機率**。

### 3.2 情報戰方程式 (Minimax of Information Warfare)
這是 BCC 最核心的突破。在決定下一步行動時，BCC 會計算**夏農資訊熵 (Shannon Entropy)** 的變化量，我們稱之為 **資訊價值 (Value of Information, VoI)**。

AI 出牌或叫牌的**總體期望效用 ($\mathcal{U}$)** 定義為：

$$ \mathcal{U}(b) = EV_{base}(b) + \alpha \cdot VoI(b, Partner) - \beta \cdot VoI(b, Opponents) $$

*   **$EV_{base}$**：該行動的物理/建設性期望值。
*   **$\alpha \cdot VoI(Partner)$**：搭檔獲得情報後的預期收益（啟蒙效應）。
*   **$\beta \cdot VoI(Opponents)$**：對手獲得情報後的預期收益（洩漏代價）。

### 3.3 湧現的「戰術隱瞞」與「假叫」
透過這條方程式，AI 不需要人類教導「何時該騙人」。
如果 AI 計算出：誠實叫牌會讓莊家的資訊熵暴跌（看透我方底牌），且 $\beta \cdot VoI(Opp) \gg \alpha \cdot VoI(Partner)$ 時，方程式的收益將變為負值。**此時，AI 的數學本能會自動推翻 BBDSL 的常規，選擇「Pass（保持靜默）」或發射「假信號（Falsecarding）」。**

---

## 4. 系統架構與機器學習整合

為了解決即時運算的效能問題，BBDSL & BCC 系統最終將與現代深度學習（Deep Learning）整合：

1. **信念網路 (Belief Network)**：取代純粹的粒子濾波，使用 Transformer 架構讀取 BBDSL 與叫牌歷史，直接輸出四家牌的潛在機率矩陣。
2. **價值網路 (Value Network)**：輸入機率矩陣，瞬間輸出 $EV$ 與 $VoI$ 估算值。
3. **ISMCTS (資訊集蒙地卡羅樹搜尋)**：在決策的葉節點上進行前瞻搜尋，尋找 Minimax 賽局的納什均衡。

---

## 5. 專案路線圖 (Roadmap)

我們將這個宏大的願景分為四個開源開發階段：

*   [X] **Phase 1: 基礎建設 (The Foundation)**
    *   完成 BBDSL YAML 規格的 JSON Schema 驗證器。
    *   開發 Python 版本的 BBDSL Parser。
*   [ ] **Phase 2: 貝氏推演 POC (The Bayesian Brain)**
    *   實作輕量級粒子濾波器，能讀取 BBDSL 進行「多輪叫牌機率坍縮」的視覺化終端機工具。
*   [ ] **Phase 3: 賽局環境與強化學習沙盒 (The Sandbox)**
    *   將系統封裝為相容於 `PettingZoo` / `OpenSpiel` 的多智能體強化學習 (MARL) 環境。
*   [ ] **Phase 4: 自我對弈與超人 AI (Self-Play)**
    *   訓練並釋出第一版搭載 BCC 引擎的開源神經網路權重。

---

## 6. 加入我們 (Call to Action)

這個計畫正處於從「理論構想」轉向「程式碼實作」的激動人心時刻。我們正在尋找以下領域的貢獻者：

*   🃏 **橋牌專家 / 國手**：協助我們撰寫並完善各種制度的 BBDSL YAML 檔案。
*   🐍 **Python / C++ 開發者**：參與 Parser、粒子濾波器以及終端模擬器的開發。
*   🧠 **AI / 機器學習研究員**：探討如何將這套貝氏推演與 Transformer / MCTS 架構結合。

歡迎在 GitHub 提交 Issue、討論架構，或直接發起 Pull Request！

> **"In the game of imperfect information, silence is a calculated vector, and deception is just advanced mathematics."**
> *(在不完全資訊的賽局中，沉默是經過計算的向量，而欺騙不過是高階的數學。)*

---
*License: MIT License*

---

## 7. BBDSL 實作進度（Implementation Status）

> 本節記錄 `bbdsl/` Python 套件的實際開發進度，對應 `BBDSL_IMPLEMENTATION-PLAN.md` 的 5 Phase 路線圖。

### 整體架構

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
Schema+MVP       實戰價值          視覺化+教學       AI 整合           社群平台
(完成)            (完成)            (完成)            (完成)            (待開發)
```

**當前狀態**：Phase 4.3 全數完成 ✅　|　851 個測試通過　|　82% 覆蓋率

---

### Phase 1 — 基礎建設（✅ 完成）

| Sprint | 交付物 | 狀態 |
|--------|--------|------|
| 1.1 | Pydantic v2 模型（`models/`）、YAML Loader、精準制範例 | ✅ |
| 1.2 | `foreach_suit` 展開器、14 條語義驗證規則（`val-001`～`val-014`） | ✅ |
| 1.3 | BML 匯入器（`bbdsl import bml`）、`UnresolvedNode` 機制 | ✅ |

### Phase 2 — 實戰價值（✅ 完成）

| Sprint | 交付物 | 狀態 |
|--------|--------|------|
| 2.1 | BBOalert 匯出器 + 匯入器 | ✅ |
| 2.2 | BML 匯出器、Selection Rules 引擎（`bbdsl select`）、`val-013/014` | ✅ |
| 2.3 | SAYC + 2/1 GF 範例制度、`val-001/003/009/010` 完整實作 | ✅ |

### Phase 3 — 視覺化與教學（✅ 完成）

| Sprint | 交付物 | 狀態 |
|--------|--------|------|
| 3.1 | 互動式 HTML Viewer（`bbdsl export html`） | ✅ |
| 3.2 | Convention Card（`bbdsl export convcard`）、SVG 叫牌樹（`bbdsl export svg`） | ✅ |
| 3.3 | 手牌產生器、練習題產生器（`bbdsl quiz`）、互動式 HTML Quiz | ✅ |

### Phase 4 — AI 整合（✅ 完成）

| Sprint | 交付物 | 狀態 |
|--------|--------|------|
| 4.1 | AI 知識庫匯出（`bbdsl export ai-kb`）、Dealer script 雙向橋接（`bbdsl export dealer`） | ✅ |
| 4.2 | 模擬對練引擎（`bbdsl simulate`）：52 張隨機發牌 + 完整叫牌拍賣模擬 | ✅ |
| 4.3 | 制度比較器（`bbdsl compare`）、PBN 牌譜匯出（`bbdsl export pbn`） | ✅ |

### Phase 5 — 社群平台（🔲 待開發）

Phase 5（線上 Registry、Web 編輯器、Diff/Merge、LIN 整合）將以獨立 repo 形式開發，以本套件作為核心依賴。

---

### 快速開始

```bash
# 安裝（使用 uv）
pip install uv
uv sync

# 驗證精準制制度（應通過全部 14 條規則）
uv run bbdsl validate examples/precision.bbdsl.yaml

# 模擬 10 副叫牌（精準制）
uv run bbdsl simulate examples/precision.bbdsl.yaml --deals 10 --seed 42

# 比較精準制 vs SAYC（50 副，輸出 JSON 報告）
uv run bbdsl compare examples/precision.bbdsl.yaml examples/sayc.bbdsl.yaml \
    --deals 50 --seed 42 -o report.json

# 匯出 PBN 牌譜
uv run bbdsl export pbn examples/precision.bbdsl.yaml --deals 5 --seed 42 -o out.pbn
```

完整 CLI 說明請參閱 [`CLAUDE.md`](./CLAUDE.md) 或執行 `uv run bbdsl --help`。
