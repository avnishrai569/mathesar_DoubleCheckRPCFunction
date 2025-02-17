<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  import portal from '@mathesar-component-library-dir/common/actions/portal';
  import Window from '@mathesar-component-library-dir/window/Window.svelte';

  import type { ModalCloseAction, ModalWidth } from './modalTypes';

  const dispatch = createEventDispatcher();

  export let modalId: number | string | undefined = undefined;
  export let isOpen = false;
  export let title: string | undefined = undefined;
  export let size: ModalWidth = 'regular';
  export let allowClose = true;
  export let hasOverlay = true;
  export let closeOn: ModalCloseAction[] = ['button'];
  export let canScrollBody = true;

  $: closeOnButton = allowClose && closeOn.includes('button');
  $: closeOnEsc = allowClose && closeOn.includes('esc');
  $: closeOnOverlay = allowClose && closeOn.includes('overlay');

  function close() {
    isOpen = false;
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && isOpen && closeOnEsc) {
      close();
    }
  }

  function handleOverlayClick() {
    if (closeOnOverlay) {
      close();
    }
  }

  async function dispatchOpenOrClose(_isOpen: boolean) {
    await tick();
    dispatch(_isOpen ? 'open' : 'close');
  }

  $: void dispatchOpenOrClose(isOpen);
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <div class="modal" data-modal-id={modalId} use:portal>
    {#if hasOverlay}
      <div
        class="overlay"
        on:click={handleOverlayClick}
        in:fade={{ duration: 150 }}
        out:fade={{ duration: 150 }}
      />
    {/if}
    <div
      class="window-positioner"
      class:width-regular={size === 'regular'}
      class:width-medium={size === 'medium'}
      class:width-large={size === 'large'}
      in:fly={{ y: 20, duration: 150 }}
      out:fly={{ y: 20, duration: 150 }}
    >
      <Window {canScrollBody} hasCloseButton={closeOnButton} on:close={close}>
        <div slot="title"><slot name="title" />{title ?? ''}</div>
        <slot />
        <slot name="footer" slot="footer" />
      </Window>
    </div>
  </div>
{/if}
