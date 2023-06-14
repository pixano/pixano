<script lang="ts">
  /**
    @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
    @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
    @license CECILL-C

    This software is a collaborative computer program whose purpose is to
    generate and explore labeled data for computer vision applications.
    This software is governed by the CeCILL-C license under French law and
    abiding by the rules of distribution of free software. You can use, 
    modify and/ or redistribute the software under the terms of the CeCILL-C
    license as circulated by CEA, CNRS and INRIA at the following URL

    http://www.cecill.info
  */

  // Imports
  import { colors } from "./utils";
  import { beforeUpdate } from "svelte";

  // Represents the classes and items present on the image
  export let items = {};
  let classes = [];

  beforeUpdate(() => {
    classes = Object.keys(items);
  });

  /**
   * Open or closes a class dropdown.
   * @param cls the class
   * @param force_open true if we want to open it, false if we want to toggle it
   */
  function toggleClassDropdown(cls: string, force_open = false) {
    // Get HTML elements
    let div = document.getElementById(`cls-${cls}`) as HTMLDivElement;
    let arrow = document.getElementById(`cls-${cls}-arrow`) as HTMLSpanElement;

    if (div) {
      if (force_open || div.style.display == "none") {
        // Open dropdown
        div.style.display = "block";
        arrow.style.rotate = "90deg";
      } else {
        // Close dropdown
        div.style.display = "none";
        arrow.style.rotate = "0deg";
      }
    }
  }

  // Adds a class to the class list
  function addClass() {
    // Get HTML input element
    let newClassInput = document.getElementById("name") as HTMLInputElement;

    let className = "";
    if (newClassInput.value != "") className = newClassInput.value;
    else className = `class-${classes.length}`;

    // Check if class name not already used
    // We should also check if empty (trimed) or forbidden chars...
    if (!classes.includes(className)) {
      classes.push(className);
      items[className] = [];
    }
    newClassInput.value = "";

    // Hack so svelte recognizes that the list was changed
    let newClasses = classes;
    classes = newClasses;
  }

  // Removes a class from the class list
  function deleteClass(cls: string) {
    const index = classes.indexOf(cls);
    if (index > -1) classes.splice(index, 1);

    // Hack so svelte recognizes that the list was changed
    let newClasses = classes;
    classes = newClasses;
  }

  // Adds an element to a class
  function addElem(cls: string) {
    //fire onValidate event
    //TODO
    //TMP: add a fake item (ajut de l'item devra etre fait dans le onValidate)
    const nb = items[cls].length;
    items[cls].push(`${cls}-${nb}`);

    // Open class dropdown
    toggleClassDropdown(cls, true);

    // Hack so svelte recognizes that the list was changed
    let newItems = items;
    items = newItems;
  }

  // Deletes an element from a class
  function deleteElem(cls: string, elem: string) {
    const index = items[cls].indexOf(elem);
    if (index > -1) items[cls].splice(index, 1);

    // Hack so svelte recognizes that the list was changed
    let newItems = items;
    items = newItems;
  }

  function handlePressEnter(event: KeyboardEvent) {
    if (event.key == "Enter") addClass();
  }
</script>

<div
  class="w-60 max-h-[90vh] overflow-y-auto absolute top-1/2 -translate-y-1/2 right-4 px-2
  bg-zinc-50 border rounded-lg shadow-lg dark:bg-zinc-800 dark:text-zinc-100 dark:border-zinc-700"
>
  {#each classes as cls, i}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="my-2 py-1 px-2 items-center border rounded select-none dark:border-zinc-700"
    >
      <!-- Class Heading -->
      <div
        class="flex flex-row cursor-pointer items-center space-x-2"
        on:click={() => {
          toggleClassDropdown(cls);
        }}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
          class="w-4 h-4"
          id="cls-{cls}-arrow"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M8.25 4.5l7.5 7.5-7.5 7.5"
          />
        </svg>
        <div class="w-full flex flex-row items-center space-x-2">
          <span
            class="w-4 h-4 flex items-center justify-center bg-[{colors[
              i
            ]}] rounded-full text-zinc-50 font-bold text-xs"
          >
            {items[cls].length}
          </span>
          <span class="font-bold w-24 grow overflow-x-auto">{cls}</span>
          <button
            on:click={(evt) => {
              evt.stopPropagation();
              deleteClass(cls);
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="1.5"
              stroke="currentColor"
              class="w-4 h-4 hover:stroke-rose-500"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
              />
            </svg>
          </button>

          <button
            on:click={(evt) => {
              evt.stopPropagation();
              addElem(cls);
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="1.5"
              stroke="currentColor"
              class="w-6 h-6 fill-[{colors[i]}]"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Class items -->
      <div
        id="cls-{cls}"
        class="flex-column mt-1 pl-4 pr-1 border-t dark:border-zinc-700"
        style="display:none"
      >
        {#each items[cls] as item}
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium py-1">{item}</div>

            <button on:click={() => deleteElem(cls, item)}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke-width="1.5"
                stroke="currentColor"
                class="w-4 h-4 cursor-pointer hover:stroke-rose-500"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                />
              </svg>
            </button>
          </div>
        {/each}
      </div>
    </div>
  {/each}
  <div
    class="w-full my-2 py-1 px-2 flex flex-col border rounded dark:border-zinc-700"
  >
    <input
      id="name"
      class="py-1 bg-inherit text-sm font-medium text-center outline-none dark:border-zinc-700"
      type="text"
      placeholder="new class"
      on:keydown={handlePressEnter}
    />
  </div>
</div>
