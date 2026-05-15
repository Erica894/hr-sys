from rest_framework.routers import DefaultRouter
from apps.hr_master.views import (
    CategorySchemeViewSet,
    EmployeeCategoryViewSet,
    EmployeeCategoryAssignmentViewSet,
)

router = DefaultRouter()
router.register("category-schemes", CategorySchemeViewSet, basename="category-scheme")
router.register("employee-categories", EmployeeCategoryViewSet, basename="employee-category")
router.register("employee-category-assignments", EmployeeCategoryAssignmentViewSet, basename="employee-category-assignment")

urlpatterns = router.urls
