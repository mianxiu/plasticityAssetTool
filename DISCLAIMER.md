# 第三方声明与使用风险说明

plasticity asset tool 是独立开发的第三方工具，非 Plasticity 官方产品。项目目前未取得官方针对本工具注入与内部接口调用方式的明确授权，不代表 Plasticity 或其开发团队，也不宣称获得其认可或支持。

内嵌模式会修改 Plasticity 的程序入口、注入自有脚本并调用内部接口。它可能因宿主版本更新而失效，也可能出现启动异常、连接失败、计算错误或数据损失。软件提供恢复备份和事务保护，但不保证在所有故障情况下均能恢复。

安装和使用前，请确认所需软件许可及集成权限，阅读宿主软件适用的授权条款，备份建模文档、组件数据库与插件恢复文件，并先在独立测试文档中验证。遇到断连或操作结果不明时，先检查视口，不要重复投递置入或布尔操作。

本软件按现状提供，不保证兼容性、稳定性、适用性或计算结果。在适用法律允许的范围内，担保排除与责任限制依照 [GPLv3 第 15、16 条](LICENSE)（官方另行授权时见 [OFFICIAL-LICENSE.md](OFFICIAL-LICENSE.md)）执行；本说明不排除依法不能排除的责任。

本说明不是官方授权或法律意见，也不能使未经授权的修改、逆向或其他行为自动合法。项目的开源许可证只适用于项目有权授权的内容，不授予 Plasticity、其内核或第三方素材的使用权。用户模型与组件的授权取决于其作者及素材本身。

本说明用于披露项目身份、技术风险与许可边界，不增加“禁止商用”“仅限学习”等与适用许可证不一致的使用限制，不修改或替代适用许可证条款。

## Third-party notice and usage risks

plasticity asset tool is an independently developed third-party tool, not an official Plasticity product. The project has not obtained explicit official authorization for its code injection and use of internal APIs. It does not represent Plasticity or its development team and does not claim their endorsement or support.

Embedded mode modifies Plasticity's application entry point, injects project scripts and calls internal APIs. Host updates may break compatibility. Startup failures, connection failures, incorrect calculations and data loss are possible. Backups and transaction safeguards do not guarantee recovery from every failure.

Before installation or use, confirm the necessary software licenses and integration permissions, review the applicable host terms, back up documents, component data and restoration files, and test with a separate document. After a disconnect or an uncertain result, inspect the viewport before repeating any insertion or boolean operation.

The software is provided as is. Compatibility, stability, fitness for a particular purpose and calculation results are not guaranteed. Warranty exclusions and limitations of liability are governed, to the extent permitted by applicable law, by GPLv3 sections 15 and 16 or, when relying on the separate official permission, by OFFICIAL-LICENSE.md. This notice does not exclude liability that cannot legally be excluded.

This notice is neither official permission nor legal advice. It does not authorize otherwise unauthorized modification, reverse engineering or other conduct. The project's license grants rights only to material the project is entitled to license; it grants no rights to Plasticity, its kernel or third-party assets. User models retain their own applicable permissions.

This notice adds no noncommercial, research-only or other use restrictions inconsistent with the applicable license, and does not amend or replace that license.
