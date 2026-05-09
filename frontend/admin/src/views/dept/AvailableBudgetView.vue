<template>
  <el-container direction="vertical" style="padding: 16px">
    <h3 style="margin: 0 0 12px">本部门可用预算</h3>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="施工中 — Sprint 2 交付"
      description="将显示：本部门在当前调薪方案下的可用预算（按 4 维矩阵：年度/晋升 × 管理干部/员工），已分配额、剩余额、使用率进度条。依赖后端预算模型加 department 维度。"
    />
  </el-container>
</template>
