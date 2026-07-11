#include "util.h"
#include "z64.h"
#include "actor.h"

extern char C_HEAP[];
extern char PAYLOAD_START[];
void* heap_next = NULL;
static char* heap_limit = NULL;

void heap_init() {
    heap_next = &C_HEAP[0];
    // Standard builds place C_HEAP after the payload and keep the historical
    // unbounded bump allocator. Extended-memory branches may place C_HEAP
    // before PAYLOAD_START; in that layout, prevent allocations from crossing
    // into the payload.
    heap_limit = ((uint32_t)C_HEAP < (uint32_t)PAYLOAD_START) ? PAYLOAD_START : NULL;
}

void* heap_alloc(int bytes) {
    int rem = bytes % 16;
    if (rem) bytes += 16 - rem;

    char* next = (char*)heap_next + bytes;
    if (heap_limit != NULL && next > heap_limit) {
        return NULL;
    }

    void* result = heap_next;
    heap_next = next;
    return result;
}

void file_init(file_t* file) {
    file->buf = heap_alloc(file->size);
    read_file(file->buf, file->vrom_start, file->size);
}

void* resolve_overlay_addr(void* addr, uint16_t overlay_id) {
    ActorOverlay overlay = gActorOverlayTable[overlay_id];
    if (overlay.loadedRamAddr) {
        return addr - overlay.vramStart + overlay.loadedRamAddr;
    }
    return NULL;
}
