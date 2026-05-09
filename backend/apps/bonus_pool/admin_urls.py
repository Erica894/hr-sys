from rest_framework.routers import DefaultRouter
from apps.bonus_pool.views import BonusPlanViewSet

router = DefaultRouter()
router.register("bonus-plans", BonusPlanViewSet, basename="bonus-plan")

urlpatterns = router.urls
