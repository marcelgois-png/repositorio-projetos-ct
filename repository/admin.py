from django.contrib import admin

from .models import Building, Category, Person, Project, ProjectFile, ProjectMember, ProjectStatus, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "function", "institutional_link", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "function", "institutional_link", "email")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(ProjectStatus)
class ProjectStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "requires_end_date", "is_active")
    list_filter = ("requires_end_date", "is_active")
    prepopulated_fields = {"code": ("name",)}
    search_fields = ("name", "code")


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1
    autocomplete_fields = ("person",)


class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    extra = 0
    fields = ("title", "file_type", "discipline", "version", "status", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    can_delete = False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "visibility", "building", "sipac_url", "updated_at")
    list_filter = ("status", "visibility", "building", "categories")
    search_fields = ("name", "description", "building__name", "location", "requested_by", "sipac_url")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories",)
    inlines = (ProjectMemberInline, ProjectFileInline)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "file_type", "discipline", "version", "status", "uploaded_at")
    list_filter = ("file_type", "discipline", "status", "uploaded_at")
    search_fields = ("title", "project__name", "description", "original_filename")
    readonly_fields = ("original_filename", "size", "uploaded_at")


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "person", "role", "responsibility", "order")
    list_filter = ("role",)
    search_fields = ("project__name", "person__name", "responsibility")
