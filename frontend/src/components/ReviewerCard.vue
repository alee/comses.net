<template>
  <div class="card mb-3">
    <div class="card-header d-flex justify-content-between align-items-center">
      <h5 class="card-title mb-0">
        {{ reviewer.memberProfile.name }}
        (<a :href="reviewer.memberProfile.profileUrl" target="_blank">{{
          reviewer.memberProfile.username
        }}</a
        >)
      </h5>
      <span>
        <a v-if="reviewer.isActive" class="btn btn-link" @click="emit('edit')">
          <small><i class="fas fa-edit me-1"></i>Edit</small>
        </a>
        <a
          v-if="reviewer.isActive"
          class="btn btn-link text-danger"
          @click="changeActiveState(reviewer, false)"
        >
          <small><i class="fas fa-trash me-1"></i>Deactivate</small>
        </a>
        <a v-else class="btn btn-link" @click="changeActiveState(reviewer, true)">
          <small><i class="fas fa-sync-alt me-1"></i>Reactivate</small>
        </a>
      </span>
    </div>
    <div class="card-body">
      <p v-if="reviewer.isActive" class="card-text">
        <strong>Email:</strong> {{ reviewer.memberProfile.email }}<br />
        <strong>Programming Languages:</strong> {{ reviewer.programmingLanguages.join(", ") }}<br />
        <strong>Subject Areas:</strong> {{ reviewer.subjectAreas.join(", ") }}<br />
        {{ reviewer.notes }}
      </p>
      <p v-else class="card-text text-muted">This reviewer is currently inactive.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Reviewer } from "@/types";
import { useReviewEditorAPI } from "@/composables/api";

const props = defineProps<{ reviewer: Reviewer }>();
const emit = defineEmits<{
  edit: [];
  changeActiveState: [Reviewer];
}>();

const { updateReviewer: update } = useReviewEditorAPI();

async function changeActiveState(reviewer: Reviewer, isActive: boolean) {
  // FIXME: Make server accept partial reviewer object without defining memberProfileId
  const response = await update(reviewer.id, {
    memberProfileId: reviewer.memberProfile.id,
    isActive,
  });
  emit("changeActiveState", response.data);
}
</script>
