<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 12px">我的薪酬</h3>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="施工中 — Sprint 2 交付"
      description="将提供：按周期查询本人月薪 / 年度奖金 / RSU 授予 / 年度薪酬总包（TC），以及按年度看激励指标变化趋势图。依赖后端补：月薪版本化、Bonus 授予表、/api/me/compensation-history/ 汇总接口。"
    />
  </el-container>
</template>
