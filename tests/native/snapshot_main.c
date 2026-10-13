/* Draws one overlay frame from a real exporter state file through the logging GDI stubs
   (gdi_log.c). Usage: snapshot <state file> <selected pid> <face picker open 0/1> */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){ if(argc<3){printf("usage\n");return 2;} g_overlay=(HWND)1; init_fonts(); scpy(g_state_path,argv[1],512);
 if(!load_state()){ printf("load_state failed\n"); return 1; }
 g_tab=1; g_player_view=1; g_selected_pid=atoi2(argv[2]); g_pending_pid=g_selected_pid; g_detail_loading=0;
 g_fp_open=argc>3?atoi2(argv[3]):0; g_detail_tab=argc>4?atoi2(argv[4]):0; g_fp_need_scroll=g_fp_open; g_mouse_x=-1; g_loaded=1;   /* as just opened */
 printf("pid=%d detail=%d fp_pid=%d faces=%d regions=%d enabled=%d\n",g_selected_pid,g_detail.id,g_fp_pid,g_face_count,g_fp_reg_count,g_faces_enabled);
 draw((HDC)0); printf("fp_scroll=%d\n",g_fp_scroll); return 0; }
