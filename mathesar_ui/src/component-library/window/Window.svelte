<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  import Button from '@mathesar-component-library-dir/button/Button.svelte';
  import { iconClose } from '@mathesar-component-library-dir/common/icons';
  import Icon from '@mathesar-component-library-dir/icon/Icon.svelte';

  const dispatch = createEventDispatcher();

  export let title: string | undefined = undefined;
  export let hasCloseButton = true;
  export let canScrollBody = true;
  export let hasBodyPadding = true;

  function handleCloseButtonClick() {
    dispatch('close');
  }
</script>

<div
  class="window"
  class:can-scroll-body={canScrollBody}
  class:has-body-padding={hasBodyPadding}
>
  {#if $$slots.title || title || hasCloseButton}
    <div class="title-bar">
      <div class="title">
        <slot name="title" />
        {title ?? ''}
      </div>
      {#if hasCloseButton}
        <Button
          appearance="plain"
          class="close-button"
          on:click={handleCloseButtonClick}
        >
          <Icon {...iconClose} />
        </Button>
      {/if}
    </div>
  {/if}
  <div class="body"><slot /></div>
  <div class="footer"><slot name="footer" /></div>
</div>
