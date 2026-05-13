<template>
  <div class="hr-page">
    <PageHeader
      title="我的薪酬"
      subtitle="个人薪酬历史、年度总包与未来 RSU vesting"
    />
    <ComingSoonCard
      title="员工自查精装即将上线"
      expected="预计 Sprint 2（约 1 周）"
      description="将按 reward cycle 展示您的全口径薪酬，包括月薪、年终奖、RSU 授予与未来归属。"
      :bullets="[
        '按 Y-2 / Y-1 / Y / Y+1 时间线一行一年展示总包（TC）',
        '未来 RSU vesting 时间轴（Y+1 ~ Y+4 待归属股数）',
        '币种统一以 CNY 折算（按周期锁定汇率）',
        '绩效评分不展示给员工本人'
      ]"
    />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ComingSoonCard from "@/components/ComingSoonCard.vue"
</script>
