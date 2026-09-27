# RULE-003 硬關與軟關（新開倉閘門）

## 1. 目的
釐清什麼情況「0 股、不能新開倉」（硬關），什麼情況「仍可買但最多新開 1 檔」（軟關），以及和「縮小預算池」的差別。

## 2. 適用範圍
紙上**新開倉**閘門（
ews_risk.gate_new_entries）；舊倉不因新聞自動平倉。預算池大小另見 RULE-002。

## 3. 規則

### 硬關（lock_new、max_new_entries = 0）
1. **戰爭級詞**／war_lock。
2. **盤崩 price_pause**：TWII 1 日 ≤ −1.5% 或 3 日 ≤ −3%。
3. **新聞全抓失敗**（unknown）。
4. 該檔標題出現**出口管制／禁運／制裁**等個股硬關。
5. 大盤熱度為 **hot 或 severe，且當日收黑（red_day，收盤 < 昨收）**。

### 軟關（soft_cap、max_new_entries = 1）
- 熱度為 **hot／severe，但沒有觸發上面的硬關**（例如只是熱、盤沒崩、也沒戰爭級）→ **仍可新開，但當天最多新開 1 檔**。
- 這是「檔數上限」，與 RULE-002 的預算池％是兩層：先過閘門，再算池多大、怎麼分。

### 非硬關／非軟關
- cool／cooling 等較涼熱度：一般不鎖檔數（max_new_entries 不設 1）；池大小仍依 RULE-002。

## 4. 注意
- severe／hot **本身**先縮預算池；要不要硬關還看有沒有收黑或其他 HARD 條件。
- old_switch_would_block、would_flat 可能只寫 journal，不代表現在真砍倉。
