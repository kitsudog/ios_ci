# Register your models here.
from datetime import datetime

from django.contrib import admin
from django.utils.html import format_html

from apple.models import IosProjectInfo, IosAccountInfo, TaskInfo, IosProfileInfo

admin.site.site_title = "打包后台"
admin.site.site_header = "打包后台"
admin.site.index_title = "打包后台"


@admin.register(IosProjectInfo)
class IosProjectInfoAdmin(admin.ModelAdmin):
    list_display_links = ['project']
    list_display = ('project', 'bundle_prefix')
    list_editable = ['bundle_prefix']
    search_fields = ('project',)
    fieldsets = (
        ['基本信息', {
            'fields': ('project', 'bundle_prefix'),
        }],
        ['额外信息', {
            'classes': ('collapse',),
            'fields': ('capability',),
        }]
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.sid = form.data["project"]
            obj.save()
        else:
            super().save_model(request, obj, form, change)


@admin.register(IosAccountInfo)
class IosAccountInfoAdmin(admin.ModelAdmin):
    list_display = ('account', 'devices_num')
    search_fields = ('account',)
    list_per_page = 10
    ordering = ('-devices_num',)
    fieldsets = (
        ['基本信息', {
            'fields': ('account', 'password'),
        }],
        ['额外信息', {
            'classes': ('collapse',),
            'fields': ('phone',),
        }]
    )


@admin.register(IosProfileInfo)
class IosProfileInfoAdmin(admin.ModelAdmin):
    list_display = ['project', 'devices_num']
    readonly_fields = ["project", "devices", "devices_num", "profile", "profile_id", "expire"]
    fieldsets = (
        ['基本信息', {
            'fields': ["project", "devices", "devices_num", "profile_id", "expire"],
        }],
    )


@admin.register(TaskInfo)
class TaskInfoAdmin(admin.ModelAdmin):
    list_filter = ['state']
    search_fields = ('uuid', 'worker')
    list_display = ('uuid', 'worker', 'human_state', 'human_expire')
    date_hierarchy = 'expire'

    # fk_fields = ('uuid',)

    def human_expire(self, _info):
        end_date = _info.expire
        if end_date >= datetime.now():
            ret = '未过期'
            color_code = 'green'
        else:
            ret = '已过期'
            color_code = 'red'
        return format_html(
            '<span style="color: {};">{}</span>',
            color_code,
            ret,
        )

    human_expire.short_description = '是否已过期'
    human_expire.admin_order_field = 'expire'

    def human_state(self, _info):
        return _info.state

    human_state.short_description = "状态"

    # noinspection PyUnusedLocal
    def restart(self, request, queryset):
        self.message_user(request, "执行完毕")

    restart.short_description = "重提提交任务"
    actions = ['restart']
