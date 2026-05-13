<template>
  <div class="hr-page">
    <PageHeader
      title="本部门可用预算"
      subtitle="部门级 4 维预算矩阵的当前余额与使用率"
    />
    <ComingSoonCard
      title="部门预算视图升级中"
      expected="可使用「我的预算」临时替代"
      description="当前可在「我的预算」页面查看部门已下发的调薪与 RSU 额度。该页面将提供更详细的部门级展开视图。"
      :bullets="[
        '4 维矩阵展示（年度 / 晋升 × 管理 / 员工）',
        '已分配 / 剩余 / 使用率进度条',
        '历史回收记录',
        '与公司池下发额度联动'
      ]"
    />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ComingSoonCard from "@/components/ComingSoonCard.vue"
</script>
