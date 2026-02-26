# 橋牌叫牌制度描述語言（DSL）現況調查報告

## 調查日期：2026-02-26

---

## 1. 摘要

目前橋牌界**沒有**一個被廣泛採用的、結構化且機器可驗證的叫牌制度描述語言。
現有方案可分為四大類：

| 類別 | 代表 | 重點 | 限制 |
|------|------|------|------|
| 牌局記錄格式 | PBN, RBN, LIN | 記錄實際打過的牌局 | 不描述制度本身 |
| 叫牌標記語言 | BML | 人類可讀的文件撰寫 | 無結構化語義，無法機器驗證 |
| 自動提醒系統 | BSS/Full Disclosure, BBOalert | BBO 線上對打時自動 alert | 扁平的序列→說明映射，無語義結構 |
| 程式碼即制度 | bidding-system-as-code | 用 Kotlin DSL 描述叫牌樹 | 需要程式設計能力，非宣告式 |

以下逐一分析。

---

## 2. 牌局記錄格式（Game Record Formats）

### 2.1 PBN — Portable Bridge Notation
- **來源**：Tis Veugen，1990 年代末，受棋類 PGN 啟發
- **官網**：https://www.tistis.nl/pbn/
- **用途**：記錄牌局的發牌、叫牌過程、出牌過程、結果
- **格式**：tag-value 對（類似 PGN），ASCII 文字檔
- **範例**：
  ```
  [Dealer "N"]
  [Vulnerable "NS"]
  [Deal "N:KQT2.AT3.J764.K8 ..."]
  [Auction "N"]
  1D Pass 1S Pass
  2S Pass 4S Pass
  Pass Pass
  ```
- **限制**：
  - 記錄的是「實際發生的叫牌」，不是「叫牌制度的規則」
  - 無法表達「如果拿到這種牌應該叫什麼」
  - 沒有語義資訊（不知道 1D 是自然叫還是人工叫）
  - 擴充性差（PBN 作者自己也承認）

### 2.2 RBN — Richards Bridge Notation
- **來源**：Richard Pavlicek
- **用途**：類似 PBN 但更緊湊，支援叫牌測驗（Y = Your call?）
- **特點**：支援標註（! = good, ? = poor, * = conventional）
- **限制**：同 PBN，專注牌局記錄而非制度描述

### 2.3 LIN — Bridge Base Online Format
- **來源**：BBO 私有格式
- **用途**：BBO 線上比賽的牌局記錄（bridge movies）
- **限制**：私有格式，文件有限，同樣不描述制度

### 2.4 Thomas Andrews 的 XML 方案
- **來源**：bridge.thomasoandrews.com/xml/
- **用途**：嘗試用 XML 取代 PBN 來表示橋牌文件
- **現況**：概念驗證階段，主要用於出版排版（配合 XSLT → HTML/PDF）
- **限制**：仍然聚焦牌局記錄，非制度描述

---

## 3. 叫牌標記語言（Bidding Markup Languages）

### 3.1 BML — Bridge Bidding Markup Language ⭐重要競品
- **來源**：Erik Sjöstrand（Kungsgeten），後由 Gert-Jan Paulissen 維護
- **GitHub**：https://github.com/gpaulissen/bml / https://github.com/Kungsgeten/bml
- **用途**：用簡潔的標記語法撰寫叫牌制度文件
- **格式**：受 Emacs org-mode 啟發的文字格式
- **範例**：
  ```
  1C  Any hand with 16+ hcp
      1D  Artificial. 0--7 hcp
          1H  Any hand with 20+ hcp
      1HS 5+ suit, forcing to game (8+ hcp)
      1N  Natural game force, 8+ hcp
      2CD 5+ suit, forcing to game (8+ hcp)
      2HS 6+ suit, 5--7 hcp
  1D  Nebulous with 2+!d, 11--15 hcp
  ```
- **輸出格式**：
  - HTML（網頁展示）
  - LaTeX（PDF）
  - BSS（BBO Full Disclosure，已廢棄）
- **特點**：
  - 縮排表示叫牌層級
  - `!c !d !h !s` 轉換為花色符號
  - `1HS` 可以同時定義 1H 和 1S
  - 支援 `#COPY / #CUT / #PASTE` 重用片段（類似巨集）
  - 支援座位（seat）和身價（vulnerability）條件
- **限制**：
  - ❌ 描述是自由文字（"Any hand with 16+ hcp"），**機器無法解析語義**
  - ❌ 無法自動驗證 HCP 區間是否有重疊或遺漏
  - ❌ 無 JSON Schema 或任何形式化的約束定義
  - ❌ Convention 模組化有限（用 COPY/PASTE 巨集，非真正的引用機制）
  - ❌ 無法驅動 AI 對練或模擬

### 評估：BML 是目前最接近「叫牌制度 DSL」的東西，但本質上仍是
「格式化文件工具」，不是「語義化描述語言」。

---

## 4. 自動提醒系統（Auto-Alert Systems）

### 4.1 BSS — Full Disclosure（已廢棄）
- **來源**：BBO 官方
- **格式**：ASCII 文字檔，高度編碼化
- **用途**：在 BBO 上自動 alert 人工叫品
- **現況**：BBO 網頁版已不再支援
- **特點**：
  - 每一行是一個叫牌序列→說明的映射
  - 有花色長度和結果的編碼
  - Convention 透過指向獨立 .bss 檔案的指標來引用
- **限制**：
  - ❌ 可讀性極差（「一個字元代表一個座位」這種編碼）
  - ❌ 已被官方放棄

### 4.2 BBOalert ⭐ 活躍專案
- **來源**：Stan Maz
- **GitHub**：https://github.com/stanmaz/BBOalert
- **格式**：CSV 風格的文字檔
- **範例**：
  ```
  ,    1C,    17+HCP any distribution
  1C--,1D,    0-7 HCP negative
  1C--1D--,1H,  5+H 16+ HCP
  ```
- **特點**：
  - 瀏覽器擴充套件，支援 Chrome/Firefox
  - 自動記錄手動 alert，下次自動重現
  - 支援座位、身價條件
  - 支援萬用字元（`--` 表示 pass，`__` 表示任意叫品）
  - 多語系支援（透過 Alias）
  - 可匯入舊的 BSS 檔案
- **限制**：
  - ❌ 純粹是「序列→說明文字」的扁平映射
  - ❌ 說明是自由文字，無結構化語義
  - ❌ 不支援牌型、HCP 範圍等約束的形式化描述
  - ❌ 無法驗證制度一致性
  - ❌ 設計目標是「自動 alert」而非「制度描述」

---

## 5. 程式碼即制度（Code-as-System）

### 5.1 bidding-system-as-code ⭐ 最有野心的方案
- **來源**：phiSgr
- **GitHub**：https://github.com/phiSgr/bidding-system-as-code
- **語言**：Kotlin DSL
- **範例**：
  ```kotlin
  "1N" - "15-17 balanced" {
      "2C" - "Stayman"
      Major.suits.forEach { M ->
          "2${M.red}" - "transfer, 5+$M" {
              "2$M" - {
                  "2N" - "invite to both games"
              }
          }
      }
  }
  ```
- **特點**：
  - ✅ 用程式碼的方式處理「相似但不完全相同」的序列
  - ✅ 支援條件邏輯，明確標示對稱與不對稱之處
  - ✅ Git 版本控制，可追蹤每次約定變更
  - ✅ 輸出 JSON 樹，配合 HTML Viewer 互動展示
  - ✅ 摺疊展開、顏色標示叫牌方、hover 顯示完整序列
  - ✅ 已有 Fantunes、Heeman 等完整制度範例
- **限制**：
  - ❌ 需要 Kotlin 程式設計能力（橋牌玩家幾乎不會）
  - ❌ 說明仍是自由文字字串，無結構化語義
  - ❌ 無法機器驗證 HCP 重疊或牌型遺漏
  - ❌ 不是宣告式的（是命令式程式碼）
  - ❌ 無法直接作為 AI 的知識庫

### 評估：概念上最先進，程式設計者的切入點正確（"Code is HyperText"），
但對非程式設計師的橋牌社群來說門檻太高。

---

## 6. AI 橋牌叫牌系統（相關但非 DSL）

### 6.1 傳統規則引擎（GIB, Jack, Wbridge5）
- 手動將叫牌規則編碼為程式邏輯
- 規則是程式碼內部的（不可匯出、不可共享）
- Wbridge5 連續多年世界電腦橋牌冠軍（2005, 2007, 2008, 2016-2018）

### 6.2 神經網路方法（近年研究主流）
- 用數百萬筆實際叫牌資料訓練 RNN/DNN
- 不需要明確的制度規則，直接學習叫牌策略
- 最新研究（2024, Kita et al.）以 SL+RL 組合勝過 Wbridge5 +1.24 IMP/board
- 可支援多種叫牌制度的深度強化學習模型也已出現

### 6.3 Synrey 平台的視覺化系統
- 提供叫牌預測 + 手牌理解的視覺化
- 幫助初學者理解叫牌規則
- 但不是可共享的制度描述格式

---

## 7. 差距分析：BBDSL 的機會

| 需求 | PBN | BML | BBOalert | as-code | BBDSL |
|------|-----|-----|----------|---------|-------|
| 描述叫牌制度規則 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 結構化語義（HCP, 牌型） | ❌ | ❌ | ❌ | ❌ | ✅ |
| 機器可驗證（一致性） | ❌ | ❌ | ❌ | ❌ | ✅ |
| Convention 模組化 | ❌ | 弱 | ❌ | 弱 | ✅ |
| 非程式設計師可用 | ✅ | ✅ | ✅ | ❌ | ✅ |
| 視覺化展示 | ❌ | ✅ | ❌ | ✅ | 計畫中 |
| AI 知識庫 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 制度繼承與差異化 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 多語系 | ❌ | ❌ | ✅ | ❌ | ✅ |
| 約定卡自動產生 | ❌ | ✅ | ❌ | ❌ | 計畫中 |

### 核心差異化定位

BBDSL 要填補的是一個明確的空白：

> **一個宣告式的、YAML-based 的、具有結構化語義的叫牌制度描述語言，
> 讓非程式設計師也能撰寫，同時讓機器能夠解析、驗證和驅動 AI 應用。**

這在現有方案中**完全不存在**。

---

## 8. 對 BBDSL 設計的建議

基於調查結果，以下幾點值得納入設計考量：

### 8.1 從 BML 學到的
- 縮排式的叫牌樹表達很直覺，橋牌玩家容易上手
- BML 的 `1HS`（同時定義 1H 和 1S）語法糖很實用
- 需要考慮是否提供 BML → BBDSL 的轉換工具

### 8.2 從 BBOalert 學到的
- 座位（1st/2nd/3rd/4th seat）和身價（vulnerability）對叫牌意義有影響
- 競叫時對手的叫品會改變語境（萬用字元是必要的）
- 多語系是國際社群的剛需
- 考慮提供 BBDSL → BBOalert 的匯出功能（實際對打時使用）

### 8.3 從 bidding-system-as-code 學到的
- 叫牌樹的「對稱性」處理非常重要（Jacoby Transfer 兩個花色）
- 互動式 HTML Viewer 的折疊、顏色標示是很好的 UX
- Git 版本控制的價值被驗證了
- 輸出 JSON 中間格式是正確的架構決策

### 8.4 從 AI 研究學到的
- 現有 AI 系統的瓶頸之一是叫牌規則的模糊性和衝突
- 一個形式化的制度描述可以直接作為 AI 的 SL 訓練參照
- BBDSL 如果能被 AI 直接消費，將是獨特賣點

### 8.5 輸出生態系考量
- BBDSL → BML（文件）
- BBDSL → BBOalert（線上對打）
- BBDSL → WBF Convention Card（比賽用）
- BBDSL → JSON Tree → HTML Viewer（教學）
- BBDSL → 練習題產生器（訓練）
- BBDSL → AI Knowledge Base（AI 對練）

---

## 9. 結論

橋牌界目前處於一個類似軟體業早期的狀態——有各種格式但缺乏統一的語義標準。
BBDSL 的定位是成為橋牌叫牌制度的「OpenAPI Specification」：

- 像 OpenAPI 之於 REST API
- 像 DBML 之於資料庫 schema
- 像 Gherkin 之於行為規格

這恰好是 Chris 在 WA-RAPTor 中已經證明的能力——
用結構化的領域特定語言橋接人類理解與機器處理之間的鴻溝。
