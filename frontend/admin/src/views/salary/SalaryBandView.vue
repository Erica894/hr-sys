<template>
  <div class="hr-page">
    <PageHeader
      title="薪酬区间管理"
      subtitle="按职级 / 岗位的薪酬带宽、Compa-ratio 与市场分位映射"
    />
    <ComingSoonCard
      title="薪酬区间维护待开放"
      expected="预计 v1.5 迭代"
      description="MVP 不含薪酬区间维护，市场分位数据来源（外购 / 砍掉）需在 6 项业务口径中拍板。"
      :bullets="[
        '按职级 / 岗位维护 min / mid / max',
        'Compa-ratio 计算口径配置',
        '市场分位 P50 / P75 / P90 数据接入',
        '年度基准批量更新'
      ]"
    />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ComingSoonCard from "@/components/ComingSoonCard.vue"
</script>
