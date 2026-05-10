# Framework Maintenance

当用户要新增类别、修改模板、调整规则，或维护 Mosaic 的整体框架时，检查以下范围。

## 新增类别

1. 更新 `VAULT_PATH/README.md`
2. 更新 `mosaic-notes/SKILL.md` 或相关 reference
3. 新建对应模板 `VAULT_PATH/Templates/TPL - {类别名}.md`
4. 维持大写开头的英文类别命名

## 修改通用规则

以下内容变更时，同时更新 skill 与 vault 文档：

- 评分系统
- 日期格式
- YAML/frontmatter 规则
- 文件组织规则

## 修改或删除类别

- 检查 `VAULT_PATH/Library/` 中是否已有该类别的笔记
- 若重命名类别，确保模板、skill、vault 文档三处一致
- 若删除类别，先确认现存笔记的迁移方案
