/* Draws the Players list (or, given a player id, that player's page) from a real exporter state
   file through the logging GDI stubs (gdi_log.c). Usage: players_list <state file> [pid] */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){ if(argc<2){printf("usage\n");return 2;} g_overlay=(HWND)1; init_fonts(); scpy(g_state_path,argv[1],512);
 if(!load_state()){ printf("load_state failed\n"); return 1; }
 g_tab=1; g_player_view=argc>2; g_mouse_x=-1; g_loaded=1;
 if(argc>2){ g_selected_pid=atoi2(argv[2]); g_pending_pid=g_selected_pid; g_detail_loading=0; g_detail_tab=0; }
 printf("players=%d\n",g_player_count);
 draw((HDC)1); return 0; }   /* a real (non-null) DC: ps_layout only measures when given none */
