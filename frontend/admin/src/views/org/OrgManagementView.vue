<template>
  <div class="hr-page">
    <PageHeader
      title="组织及人员管理"
      subtitle="部门树、员工台账、职级岗位的统一维护入口"
    />
    <ComingSoonCard
      title="组织管理 UI 待精装"
      expected="预计 v1.5 迭代"
      description="MVP 阶段可通过后端管理命令导入 HR 主数据，UI 化的台账编辑放在 v1.5。"
      :bullets="[
        '部门树编辑（COMPANY → SUBSIDIARY → DEPT → CENTER → TEAM）',
        '员工台账 CRUD（入职、调岗、离职）',
        '岗位 / 职级 / 序列映射管理',
        '编制总数与实际占用对比'
      ]"
    />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ComingSoonCard from "@/components/ComingSoonCard.vue"
</script>
