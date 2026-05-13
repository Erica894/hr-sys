<template>
  <div class="hr-page">
    <PageHeader
      title="分配结果分析"
      subtitle="本部门调薪与 RSU 分配结果的分布、偏差、对比分析"
    />
    <ComingSoonCard
      title="部门分配分析即将上线"
      expected="预计 2026-06 月"
      description="完整的分析图与报表 UI，需用户在 2026-06-10 前完成 6 项业务口径拍板。"
      :bullets="[
        '调薪幅度分位分布（P50 / P75 / P90）',
        'RSU 授予分层与人头占比',
        '与预算目标偏差对比',
        '与同级部门横向对照',
        '历年对比窗口（Y-1 / Y / Y+1 默认口径）'
      ]"
    />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ComingSoonCard from "@/components/ComingSoonCard.vue"
</script>
