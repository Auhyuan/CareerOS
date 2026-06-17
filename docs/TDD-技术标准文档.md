# TDD - 鎶€鏈爣鍑嗘枃妗?
## 1. 鐩爣

鏈枃妗ｅ畾涔夊氨涓氭寚瀵?AI 骞冲彴 Python 渚х殑鎶€鏈爣鍑嗐€傝繖閲岀殑 TDD 鎸?Technical Design Document锛岀敤浜庣害鏉熸灦鏋勩€佷唬鐮佺粍缁囥€佹帴鍙ｃ€佹暟鎹簱銆丄gent 鏋勫缓鍜屽悗缁紨杩涙柟寮忋€?
## 2. 鏈嶅姟鍒嗗眰鏍囧噯

Python 渚у缓璁媶鎴愪袱绫诲悗绔細

| 灞傜骇 | 寤鸿鍚嶇О | 鑱岃矗 | 绀轰緥妯″潡 |
| --- | --- | --- | --- |
| 鑳藉姏灞?| `capability-backend` | 閫氱敤 AI 鍜屾暟鎹兘鍔涳紝涓嶇粦瀹氬叿浣撲笟鍔℃祦绋?| Agent銆佺埇铏€佹ā鍨嬨€佸伐鍏枫€佺煡璇嗗簱銆佹祻瑙堝櫒鑷姩鍖?|
| 缂栨帓灞?| `orchestration-backend` | 涓氬姟娴佺▼缂栨帓锛岀粍鍚堣兘鍔涘眰瀹屾垚骞冲彴浠诲姟 | 宀椾綅鐢诲儚鐢熸垚銆佺畝鍘嗗垎鏋愩€佽亴涓氳鍒?|

褰撳墠椤圭洰鍙互鍏堜繚鎸佷竴涓?FastAPI 搴旂敤锛屽悗缁寜妯″潡杈圭晫杩佺Щ銆?
## 3. 鎺ㄨ崘鐩綍鏍囧噯

鍗曚釜鏈嶅姟妯″潡寤鸿淇濇寔浠ヤ笅缁撴瀯锛?
```text
server/<module>/
  api/
    __init__.py
    xxx_api.py
  src/
    schemas/
      request.py
      response.py
    service/
    repository/
    models/
    config/
```

Agent 杩欑被澶嶆潅妯″潡鍙互缁х画缁嗗垎锛?
```text
server/agent/src/
  agent/
  model/
  tools/
  prompts/
  runtime/
  middlewares/
  memory/
  checkpoint/
  graph/
  context/
  templates/
```

## 4. 浠ｇ爜娉ㄩ噴鏍囧噯

鏍规嵁椤圭洰绾﹀畾锛?
- 姣忎釜鍑芥暟鎴栨柟娉曞繀椤绘湁娉ㄩ噴锛岃鏄庡嚱鏁颁綔鐢ㄣ€佹牳蹇冨弬鏁板拰杩斿洖鍊笺€?- 鏍稿績娴佺▼蹇呴』鍐欒缁嗘敞閲婏紝渚嬪 Agent 缁勮銆佹秷鎭竻鐞嗐€佸伐鍏锋敞鍏ャ€佹暟鎹叆搴撱€?- 娉ㄩ噴瑕佽В閲婁笟鍔℃剰鍥惧拰璁捐鍘熷洜锛屼笉鍐欐棤鎰忎箟閲嶅娉ㄩ噴銆?
## 5. API 鏍囧噯

### 5.1 缁熶竴鍝嶅簲

鎵€鏈変笟鍔℃帴鍙ｈ繑鍥烇細

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

绾﹀畾锛?
- `code=0` 琛ㄧず鎴愬姛銆?- 涓氬姟寮傚父浣跨敤鏄庣‘涓氬姟閿欒鐮併€?- 鏈煡寮傚父鐢卞叏灞€寮傚父澶勭悊鍣ㄨ浆鎹负缁熶竴鍝嶅簲銆?
### 5.2 HTTP 鏂规硶

- 鏌ヨ銆佹悳绱€佹墽琛岀被涓氬姟鎺ュ彛浼樺厛浣跨敤 POST锛屼究浜庣粺涓€鍙傛暟浣撳拰鍚庣画鎵╁睍銆?- 鍋ュ悍妫€鏌ャ€佸熀纭€閰嶇疆鏌ョ湅鍙互浣跨敤 GET銆?- 璺緞鍛藉悕浣跨敤妯″潡鍓嶇紑锛屼緥濡?`/agent/run`銆乣/spider/qcwy/jobs`銆乣/job/crawl/qcwy/jobs`銆乣/job/raw-records/search`銆?
## 6. 鏉冮檺杈圭晫鏍囧噯

Python 鏈嶅姟涓嶅仛鐢ㄦ埛鏉冮檺绠＄悊锛?
- 涓嶆帴鏀剁敤鎴锋潈闄愪笂涓嬫枃浣滀负鏍稿績涓氬姟鍒ゆ柇渚濇嵁銆?- 涓嶅疄鐜扮櫥褰曘€侀壌鏉冦€佽彍鍗曟潈闄愩€佹暟鎹潈闄愩€?- Java 灞傚畬鎴愭潈闄愭牎楠屽悗璋冪敤 Python 鎺ュ彛銆?- Python 鍙仛鍙傛暟鏍￠獙銆佷笟鍔℃墽琛屽拰缁撴灉杩斿洖銆?
## 7. Agent 鏋勫缓鏍囧噯

### 7.1 `/agent/run` 瀹氫綅

`/agent/run` 鏄€氱敤 Agent 鎵ц鍣紝涓嶇粦瀹氬叿浣撲笟鍔″拰妯℃澘銆?
璇锋眰涓笉搴斿寘鍚細

- `agent_id`
- `request_id`
- `metadata`
- `dry_run`
- 澶栭儴 `input_messages`

### 7.2 鏍稿績璇锋眰鍙傛暟

```json
{
  "query": "鏈浠诲姟鎸囦护",
  "conversation_id": "鍙€変細璇?ID",
  "system_prompt": "鍙€夌郴缁熸彁绀鸿瘝",
  "inputs": {},
  "files": [],
  "tools": [],
  "optional_features": {
    "long_term_memory_enabled": false,
    "conversation_context_enabled": false,
    "checkpoint_enabled": false,
    "deferred_tool_filter_enabled": false
  },
  "runtime_options": {
    "model": null,
    "temperature": 0.2,
    "timeout_seconds": 60,
    "max_retries": 2
  }
}
```

### 7.3 缁勮娴佺▼

AgentService 璐熻矗缁勮 Agent锛?
1. 鏋勫缓杩愯涓婁笅鏂囥€?2. 鏍规嵁妯″瀷閰嶇疆鍒涘缓 ChatOpenAI銆?3. 鏍规嵁 `tools` 绛涢€夊彲鐢ㄥ伐鍏枫€?4. 鏍规嵁鍙€夎兘鍔涜閰嶄腑闂翠欢銆?5. 鏍规嵁 `checkpoint_enabled` 瑁呴厤 PostgreSQL Checkpointer銆?6. 浣跨敤 LangChain `create_agent` 鍒涘缓 Agent銆?7. 璋冪敤鏃跺厛娉ㄥ叆 `RemoveMessage(id=REMOVE_ALL_MESSAGES)` 娓呯悊 checkpoint 涓殑鏃ф秷鎭€?8. 娉ㄥ叆 ContextService 璇诲彇鍒扮殑鍘嗗彶娑堟伅鍜屽綋鍓嶇敤鎴烽棶棰樸€?
### 7.4 ContextService 涓?Checkpoint 鍒嗗伐

| 鑳藉姏 | 浣滅敤 | 鏄惁璺ㄨ疆瀵硅瘽浣滀负鍘嗗彶 |
| --- | --- | --- |
| ContextService | 淇濆瓨鐢ㄦ埛鍙鐨勪細璇濆巻鍙诧紝渚嬪鐢ㄦ埛闂銆佹ā鍨嬪洖澶嶃€佸伐鍏锋秷鎭憳瑕?| 鏄?|
| Checkpointer | 淇濆瓨 LangGraph 鍗曟杩愯杩囩▼鐘舵€侊紝渚嬪宸ュ叿璋冪敤銆佷腑闂村彉閲忋€佸浘鐘舵€?| 鍚︼紝杩愯鍓嶆竻鐞嗘秷鎭伩鍏嶉噸澶?|

## 8. 宸ュ叿涓庝腑闂翠欢鏍囧噯

宸ュ叿璐熻矗鎵ц鍔ㄤ綔锛屼腑闂翠欢璐熻矗杩愯鏈熷寮恒€?
绀轰緥锛?
- 鐭ヨ瘑搴撳伐鍏疯礋璐ｆ绱€?- 鐭ヨ瘑搴撲腑闂翠欢璐熻矗淇濆瓨妫€绱㈢粨鏋滃埌 state锛屽苟鍦ㄤ笅涓€杞ā鍨嬭皟鐢ㄥ墠娉ㄥ叆绯荤粺鎻愮ず璇嶃€?- 宸ュ叿鍙傛暟涓笉搴旀毚闇茬粰妯″瀷鐨勫唴瀹归€氳繃 runtime context 娉ㄥ叆锛屼緥濡傜煡璇嗗簱 ID銆佷笟鍔¤繃婊ゆ潯浠躲€?
## 9. 缂栨帓灞傛爣鍑?
缂栨帓灞傝礋璐ｆ妸鑳藉姏缁勫悎鎴愪笟鍔￠棴鐜€?
宀椾綅鐢诲儚鐢熸垚绀轰緥锛?
1. 鎺ユ敹 Java 灞傚彂璧风殑宀椾綅鐢诲儚鐢熸垚璇锋眰銆?2. 鏌ヨ宀椾綅鏂瑰悜鍜岀浉鍏虫嫑鑱樻牱鏈€?3. 鏋勯€犲矖浣嶇敾鍍忓垎鏋?prompt銆?4. 璋冪敤鑳藉姏灞?`/agent/run`銆?5. 瑙ｆ瀽缁撴瀯鍖栬緭鍑恒€?6. 鍐欏叆 `job_market_profiles`銆?7. 杩斿洖浠诲姟鐘舵€佹垨鐢熸垚缁撴灉銆?
缂栨帓灞傚彲浠ユ嫢鏈夎嚜宸辩殑 API銆乻ervice銆乺epository銆乻chema锛屼笉搴旀妸娴佺▼鏁ｈ惤鍦?Agent 鎴栫埇铏ā鍧楅噷銆?
鎷涜仒鏁版嵁閲囬泦鍏ュ簱绀轰緥锛?
1. 缂栨帓灞傛帴鏀?`/job/crawl/qcwy/jobs` 璇锋眰銆?2. 缂栨帓灞傚垱寤?`spider_crawl_runs` 杩愯璁板綍銆?3. 缂栨帓灞傝皟鐢ㄨ兘鍔涘眰 `/spider/qcwy/jobs` 鑾峰彇瀹屾暣宀椾綅 rows銆?4. 缂栨帓灞傚啓鍏?`job_raw_records` 鍜?`job_raw_records`銆?5. 缂栨帓灞傛洿鏂伴噰闆嗕换鍔＄姸鎬佸苟杩斿洖鍏ュ簱缁熻銆?
鑳藉姏灞傜埇铏帴鍙ｄ笉寰楃洿鎺ヤ緷璧栧矖浣嶅簱妯″瀷锛屼篃涓嶅緱鐩存帴璋冪敤 JobService銆?
## 10. 鏁版嵁搴撴爣鍑?
- PostgreSQL 鏄綋鍓嶅敮涓€鎸佷箙鍖栫粍浠讹紝鏆備笉寮曞叆 Redis銆?- Agent 鐩稿叧琛ㄦ斁鍏?`agent` schema銆?- 宀椾綅鍜岀埇铏浉鍏宠〃褰撳墠鏀惧叆 `public` schema锛屽悗缁彲鎸夐渶瑕佹媶鎴?`job`銆乣spider` schema銆?- 鍘熷鎷涜仒鏁版嵁蹇呴』淇濈暀鍒?`job_raw_records`锛屾柟渚垮悗缁噸鏂板垎鏋愩€?- 鏍囧噯鍖栧矖浣嶆暟鎹啓鍏?`job_raw_records`銆?- 鑱氬悎鐢诲儚鍐欏叆 `job_market_profiles`銆?- JSONB 鐢ㄤ簬淇濆瓨涓嶇ǔ瀹氱粨鏋勶紝渚嬪鍘熷 JSON銆佹ā鍨嬭緭鍑恒€佹ā鏉块厤缃€?
## 11. 鍙娴嬫€ф爣鍑?
- 鏈湴鏈嶅姟鍚姩鏃跺仛 PostgreSQL 鍋ュ悍妫€鏌ャ€?- 鍏抽敭涓氬姟娴佺▼闇€瑕佽褰曟棩蹇椼€?- Agent 璋冪敤閾捐矾浼樺厛鎺ュ叆 LangSmith锛岀敤浜庡畾浣嶆ā鍨嬭皟鐢ㄣ€佸伐鍏疯皟鐢ㄥ拰鍥剧姸鎬侀棶棰樸€?- Python 灞備笉寮哄埗淇濈暀 `request_id`锛岃皟鐢ㄩ摼杩借釜浼樺厛渚濊禆 LangSmith 鍜屾湇鍔℃棩蹇椼€?
## 12. 杩佺Щ璺緞

鐭湡锛?
- 淇濇寔褰撳墠 `backend/app/main.py` 鍗曞簲鐢ㄣ€?- 鍦ㄦ枃妗ｅ拰浠ｇ爜杈圭晫涓婂尯鍒嗚兘鍔涘眰涓庣紪鎺掑眰銆?- 鏂板宀椾綅鐢诲儚鐢熸垚鏃讹紝浼樺厛鏀惧叆鐙珛缂栨帓妯″潡銆?
涓湡锛?
- 鎶藉嚭 `capability_app`锛屼繚鐣?Agent銆丼pider銆丮odel銆乀ools銆?- 鎶藉嚭 `orchestration_app`锛屾斁宀椾綅鐢诲儚銆佺畝鍘嗗垎鏋愩€佽亴涓氳鍒掋€?- 涓や釜搴旂敤鍏辩敤鏁版嵁搴撳拰閮ㄥ垎 common 宸ュ叿銆?
闀挎湡锛?
- 鑳藉姏灞傛垚涓洪€氱敤 Agent/AI 鑳藉姏骞冲彴銆?- 缂栨帓灞傛垚涓哄氨涓氭寚瀵间笟鍔℃櫤鑳戒腑鍙般€?- Java 灞備綔涓虹粺涓€涓氬姟鍏ュ彛鍜屾潈闄愭帶鍒跺眰銆?

