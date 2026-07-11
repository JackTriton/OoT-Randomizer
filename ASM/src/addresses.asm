; Pointers to game state
.definelabel SAVE_CONTEXT,      0x8011A5D0
.definelabel GLOBAL_CONTEXT,    0x801C84A0
.definelabel SUBSCREEN_CONTEXT, 0x801D8C00
.definelabel PLAYER_ACTOR,      0x801DAA30
.definelabel GET_ITEMTABLE,     0x803A9E7E

; Extended memory map:
//AUDIO_THREAD_FREE             0x8018EE60 ; size 0x37F00
;
; Keep the payload layout in this file so branches that move the payload only
; need to update these constants. If PAYLOAD_START is moved above C_HEAP, the C
; allocator in c/util.c automatically treats PAYLOAD_START as its upper bound.
.definelabel PAYLOAD_ROM_START, 0x03480000
.definelabel PAYLOAD_START,     0x80400000
.definelabel PAYLOAD_LIMIT,     0x80600000
.definelabel DEBUG_BUFFER,      0x80600000 ; size 0x1000
.definelabel C_HEAP,            0x80601000
