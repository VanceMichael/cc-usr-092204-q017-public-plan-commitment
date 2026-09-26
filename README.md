# 民生规划承诺兑现

面向公众的五年规划承诺兑现服务：把公营房屋、劣质劏房治理、公立医院病床、地区康健中心与青年项目拆成**可量化里程碑**，每项关联预算、责任机构、空间项目、公众咨询意见与证据快照。年度施政方案**只能调整实现路径，不能改写五年目标**；统计口径变化必须附可比桥接。市民可从一个目标看到最新结果、延期解释与下一节点；监督人员可重现任一时点为何被判定为按期、预警或偏离。

## 领域事实

- 五年规划量化公营房屋 196,000 个单位、轮候时间、劏房治理、病床、康健服务与青年受惠人数目标
- 规划与年度施政方案相互衔接：路径可调，目标锁定
- 编制过程收到超过 17,000 份公众意见，意见主题与采纳情况回溯到目标
- 跨部门数据迟到时当前进度标明置信状态（定稿/初步/估算/陈旧/缺报）
- 社区组织只能反馈获居民授权的去标识个案；未公开选址与个人申请信息不得外泄

## 目录说明

- `contracts/` 交换契约：`context.schema.json`、`domain.schema.json`（目标/节点/证据/修订/口径桥接/数据通知/空间项目/咨询）、`feedback.schema.json`（授权组织与反馈个案）
- `fixtures/` 去标识样例：`build_fixtures.py` 确定性生成 `domain.json`、`feedback.json`（证据哈希自动计算）
- `src/` 服务源码
  - `catalog.py` 载入并按契约校验资料
  - `validation.py` 零依赖 JSON Schema 子集校验器
  - `bridging.py` 统计口径桥接（factor/additive/平行序列，正反两向）
  - `canonical.py` 证据快照规范序列化与 SHA-256
  - `engine.py` 判定引擎 `status-rules-v1.0`（置信折算、口径换算、按期/预警/偏离、时点重放）
  - `governance.py` 目标治理（锁定、非法改写拒绝并留痕、口径变更桥接守门）
  - `views.py` 市民/监督视图、选址脱敏、社区授权与 PII 拦截
  - `service.py` / `server.py` 服务门面与 HTTP 入口
- `tests/` 53 项 unittest

## 判定与治理规则（摘要）

- **证据准入**：以系统 `received_at` 为准进入判定；未送达不计入。节点到期后有 45 日宽限，期内显示「待数据」；超宽限仍无实测，有修订确认路径调整判「偏离」，否则判「预警」。
- **置信状态**：覆盖率 <0.9 降为初步、<0.5 降为估算；迟到打标；定稿季度节点不因查询日推移而被误标陈旧。
- **口径桥接**：实测先换算到节点承诺口径再比较；最新结果同时给锁定口径等效值，保证与五年目标直接可比。
- **目标锁定**：锁定后任何带 `target_value` 的改写一律拒绝并在目标历史留痕 `rewrite_rejected`；`metric_rebaseline` 必须附桥接，且换算后目标等效值一致。
- **时点重放**：`?at=` 重放时只采用该时点前已送达的证据与已生效的修订，迟到数据与未来调整不改变历史判定。

## HTTP 接口

启动：`python3 -m src.server`（http://127.0.0.1:8000）

市民侧
- `GET /dashboard`、`GET /targets/<id>`（均支持 `?at=ISO-8601` 时点重放）
- `GET /consultations`、`GET /consultations/<id>`
- `GET /spatial-projects`（未公开选址自动脱敏到地区粒度）
- `GET /plans`、`GET /revisions`、`GET /cases/public`

监督侧（请求头 `X-Role: oversight`）
- `GET /targets/<id>/oversight`：每节点完整判定输入
- `GET /targets/<id>/replay/<milestone_id>`：规则码、口径换算轨迹、证据编号与哈希校验

社区组织（请求头 `X-Org-Code` / `X-Org-Token`）
- `GET /cases/org`：只返回本组织授权范围个案
- `POST /cases`：提交获授权的去标识个案；无授权、超范围、含个人信息（身份证/电话/申请编号）一律拒绝

## 本地检查

```bash
python3 fixtures/build_fixtures.py     # 重新生成样例（确定性）
python3 -m unittest discover -s tests -v
```

样例中的机构、地名、选址、档号与个案均为合成代号，不含任何真实个人信息。
