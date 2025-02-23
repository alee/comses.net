<template>
  <div>
    <slot name="label">
      <FieldLabel v-if="label" :label="label" :id-for="id" :required="required" />
    </slot>
    <div class="form-check-inline ms-3">
      <label class="form-check-label" :for="`${id}-custom-input-check`">
        <input
          type="checkbox"
          class="form-check-input me-1"
          v-model="showCustomInput"
          :id="`${id}-custom-input-check`"
          :disabled="disabled"
        />
        <small class="text-muted">Enter manually</small>
      </label>
    </div>
    <FormPlaceholder v-if="showPlaceholder" />
    <span v-else-if="showCustomInput">
      <div class="input-group">
        <input
          v-model="candidateCustomName"
          :id="`${id}-custom-input-name`"
          :class="['form-control', { 'is-invalid': localErrors.name }]"
          placeholder="Name (ex. Arizona State University)"
          @input="localErrors.name = ''"
          @keydown.enter.prevent="createCustom"
        />
        <input
          v-model="candidateCustomUrl"
          :id="`${id}-custom-input-url`"
          :class="['form-control', { 'is-invalid': localErrors.url }]"
          placeholder="URL (ex. http://asu.edu)"
          @input="localErrors.url = ''"
          @keydown.enter.prevent="createCustom"
        />
        <button
          type="button"
          v-if="candidateCustomName || candidateCustomUrl"
          class="btn btn-outline-secondary"
          @click="createCustom"
        >
          <small>Press enter to add</small>
        </button>
      </div>
      <FieldError
        v-if="localErrors.name || localErrors.url"
        :error="localErrorMessage"
        :id-for="id"
      />
    </span>
    <ResearchOrgField
      v-else
      name="organization"
      :placeholder="placeholder"
      :clear-on-select="true"
      @select="create"
      :disabled="disabled"
    />
    <Sortable :list="organizations" :item-key="item => item" @end="sort($event)">
      <template #item="{ element, index }">
        <div :key="element" class="my-1 input-group">
          <span class="primary-group-button">
            <button v-if="index === 0" type="button" class="btn btn-is-primary w-100">
              Primary
            </button>
            <button
              v-else
              type="button"
              class="btn btn-make-primary w-100"
              @click="sortToTop(index)"
            >
              <small>Set primary</small>
            </button>
          </span>
          <input :value="element.name" class="form-control w-25" readonly :disabled="disabled" />
          <span class="input-group-text bg-white flex-grow-1 flex-shrink-1 w-25 overflow-hidden">
            <a :href="element.url" target="_blank">{{ element.url }}</a>
          </span>
          <button
            type="button"
            class="btn btn-delete-item"
            tabindex="-1"
            @click.once="remove(index)"
            :disabled="disabled"
          >
            &times;
          </button>
        </div>
      </template>
    </Sortable>
    <slot name="help">
      <FieldHelp v-if="help" :help="help" :id-for="id" />
    </slot>
    <slot name="error">
      <FieldError v-if="error" :error="error" :id-for="id" />
    </slot>
  </div>
</template>

<script setup lang="ts">
import { inject, ref, onMounted, reactive, computed, watch } from "vue";
import { string } from "yup";
import { Sortable } from "sortablejs-vue3";
import type { SortableEvent } from "sortablejs";
import { useField } from "@/composables/form";
import ResearchOrgField from "@/components/form/ResearchOrgField.vue";
import FieldLabel from "@/components/form/FieldLabel.vue";
import FieldHelp from "@/components/form/FieldHelp.vue";
import FieldError from "@/components/form/FieldError.vue";
import FormPlaceholder from "@/components/form/FormPlaceholder.vue";
import type { Organization } from "@/types";

export interface ResearchOrgListFieldProps {
  // FIXME: extend from types/BaseFieldProps when vuejs/core#8083 makes it into a release
  name: string;
  label?: string;
  help?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  isContributorOrganization?: boolean;
}

const props = defineProps<ResearchOrgListFieldProps>();
const emit = defineEmits(["change"]);
onMounted(() => {
  if (!organizations.value) {
    // force initialize to empty array
    organizations.value = [];
  }

  // set givenName in the ContributorEditForm whenever value (selected organization) changes
  watch(
    () => organizations,
    () => {
      emit("change");
    },
    { deep: true }
  );
});

const showCustomInput = ref(false);
const candidateCustomName = ref("");
const candidateCustomUrl = ref("");
const localErrors = reactive({ name: "", url: "" });

const localErrorMessage = computed(() => {
  return `${localErrors.name}
          ${localErrors.name && localErrors.url ? "and " : ""}
          ${localErrors.url}`;
});

function validateLocal() {
  let valid = true;
  if (!candidateCustomName.value) {
    localErrors.name = "Affiliation name is required";
    valid = false;
  }
  const schema = string().url();
  if (!schema.isValidSync(candidateCustomUrl.value)) {
    localErrors.url = "Affiliation URL must be a valid URL";
    valid = false;
  }
  if (!candidateCustomUrl.value) {
    localErrors.url = "Affiliation URL is required";
    valid = false;
  }
  return valid;
}

function createCustom() {
  if (validateLocal()) {
    const customOrg: Organization = {
      name: candidateCustomName.value,
      url: candidateCustomUrl.value,
    };
    create(customOrg);
    candidateCustomName.value = "";
    candidateCustomUrl.value = "";
  }
}

function create(organization: Organization) {
  // only one organization is allowed if Contributor is Organization
  if (props.isContributorOrganization && organizations.value.length > 0) {
    organizations.value = [];
    organizations.value.push(organization);
    return;
  }

  if (!organizations.value.some(e => e.name === organization.name)) {
    organizations.value.push(organization);
  }
}

function remove(index: number) {
  organizations.value.splice(index, 1);
}

function sort(event: SortableEvent) {
  const { newIndex, oldIndex } = event;
  if (newIndex !== undefined && oldIndex !== undefined) {
    const item = organizations.value.splice(oldIndex, 1)[0];
    organizations.value.splice(newIndex, 0, item);
  }
}

function sortToTop(index: number) {
  const item = organizations.value.splice(index, 1)[0];
  organizations.value.splice(0, 0, item);
}

const { id, value: organizations, error } = useField<Organization[]>(props, "name");

const showPlaceholder = inject("showPlaceholder", false);
</script>
