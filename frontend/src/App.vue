<template>
  <div
    class="flex text-gray-900 h-screen antialiased overflow-y-hidden"
    :class="{ 'bg-slate-50': $route.meta.documentPage }"
    @contextmenu.prevent="handleDefaultContext($event)">
    <div
      class="h-full max-h-full w-full max-w-full flex flex-col"
      :class="{ 'sm:bg-gray-50': $route.meta.isPublicRoute }">
      <div
        v-if="(isLoggedIn && !isHybridRoute) || $route.meta.documentPage"
        class="flex h-full overflow-x-hidden">
        <MobileSidebar v-if="isLoggedIn" v-model="showMobileSidebar" />
        <div
          v-if="showSidebar"
          class="px-2 border-r w-[240px] bg-gray-50 hidden md:py-4 md:block">
          <Sidebar />
        </div>
        <div class="flex-1 overflow-y-auto overflow-x-hidden">
          <router-view v-slot="{ Component }">
            <Navbar
              v-if="(isLoggedIn && !isHybridRoute) || $route.meta.documentPage"
              :mobile-sidebar-is-open="showMobileSidebar"
              @toggle-mobile-sidebar="showMobileSidebar = !showMobileSidebar" />
            <component :is="Component" ref="currentPage" />
          </router-view>
        </div>
        <Transition
          enter-from-class="translate-x-[150%] opacity-0"
          leave-to-class="translate-x-[150%] opacity-0"
          enter-active-class="transition duration-700"
          leave-active-class="transition duration-700">
          <div v-if="showInfoSidebar" class="border-l md:pt-6 flex">
            <InfoSidebar :entity="$store.state.entityInfo" />
          </div>
        </Transition>
      </div>
      <router-view v-else />
    </div>
  </div>
  <div id="dropzoneElement" class="hidden" />
</template>
<script>
import Navbar from "@/components/Navbar.vue";
import Sidebar from "@/components/Sidebar.vue";
import MobileSidebar from "@/components/MobileSidebar.vue";

export default {
  name: "App",
  components: {
    Navbar,
    Sidebar,
    MobileSidebar,
  },
  data() {
    return {
      dropzone: null,
      showMobileSidebar: false,
      computedFullPath: "",
    };
  },
  computed: {
    showSidebar() {
      return this.$route.meta.sidebar !== false;
    },
    isLoggedIn() {
      return this.$store.getters.isLoggedIn;
    },
    isHybridRoute() {
      return this.$route.meta.isHybridRoute;
    },
    showUploadTracker() {
      return this.isLoggedIn && this.$store.state.uploads.length > 0;
    },
    showInfoSidebar() {
      return this.$store.state.showInfo && this.$store.state.entityInfo;
    },
  },
  watch: {
    $route() {
      this.$store.commit("setEntityInfo", null);
      this.$store.commit("setShowInfo", false);
    },
  },
  async mounted() {
    let componentContext = this;
  },
  unmounted() {
   
  },
  methods: {
    handleDefaultContext(event) {
      event.preventDefault();
    },
    async currentPageEmitTrigger() {
      await this.$refs.currentPage.triggerFetchFolderEmit();
    },
  },
};

</script>

<style>
html {
  -webkit-user-select: none;
  /* Safari */
  -ms-user-select: none;
  /* IE 10 and IE 11 */
  user-select: none;
  /* Standard syntax */
}
</style>

