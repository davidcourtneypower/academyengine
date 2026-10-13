/* v1.24.32: face picker input against a real exporter state file (picker open).
   Usage: harness <state file> <pid> <command dir/>  -- links with gdi_log.c */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){int fails=0;g_overlay=(HWND)1;init_fonts();scpy(g_state_path,argv[1],512);scpy(g_cmd_dir,argv[3],512);
 if(!load_state()){printf("load failed\n");return 1;}
 g_tab=1;g_player_view=1;g_selected_pid=atoi2(argv[2]);g_pending_pid=g_selected_pid;g_detail_loading=0;g_fp_open=1;g_loaded=1;
 if(g_fp_pid!=g_selected_pid||g_face_count<4||g_fp_reg_count<2||!g_faces_enabled){printf("state pid=%d faces=%d regs=%d\n",g_fp_pid,g_face_count,g_fp_reg_count);fails++;}
 RECT r;GetClientRect(g_overlay,&r);if(fp_page_size(&r)!=40){printf("page size %d\n",fp_page_size(&r));fails++;}
 FpGeom g;fp_geom(&r,&g);
 /* click the third tile: becomes current locally and a FACE command is written */
 char want[200];scpy(want,g_faces[2].rel,200);face_picker_click(g.gx+2*112+40,g.gy+40);
 int cur=-1;for(int i=0;i<g_face_count;i++)if(g_faces[i].current){if(cur>=0)fails++;cur=i;}if(cur!=2){printf("current %d\n",cur);fails++;}
 /* the gap under a tile (caption) is not a click */
 face_picker_click(g.gx+0*112+40,g.gy+110);if(!g_faces[2].current){printf("caption click picked\n");fails++;}
 /* v1.24.33: "Load more faces" under the grid (scroll to the bottom first) */
 g_fp_scroll=fp_max_scroll(&g);int my=fp_more_y(&g);if(my<g.gy||my+32>g.gy+g.gh){printf("load more off screen %d\n",my);fails++;}
 face_picker_click(g.gx+g.gw/2,my+10);if(!g_fp_loading_more){printf("load more not requested\n");fails++;}
 face_picker_click(g.gx+g.gw/2,my+10);  /* a second click while loading does nothing */
 g_fp_loading_more=0;g_fp_scroll=0;
 /* region row 2 */
 char reg[64];scpy(reg,g_fp_regs[1],64);if(!seq(g_fp_reg_labels[0],"Ireland")||seq(g_fp_reg_labels[2],g_fp_regs[2])){printf("labels %s / %s\n",g_fp_reg_labels[0],g_fp_reg_labels[2]);fails++;}face_picker_click(g.sx+20,g.sy+30+5);if(!seq(g_fp_region,reg)||g_fp_pid!=0||g_face_count!=0){printf("region %s\n",g_fp_region);fails++;}
 g_fp_pid=g_selected_pid;
 /* automatic face closes the picker (v1.24.33) */
 face_picker_click(g.px+g.pw-300,g.py+30);if(g_fp_open){printf("automatic did not close\n");fails++;}
 /* reopen from the header */
 face_picker_open();if(!g_fp_open||g_fp_pid!=0){printf("open\n");fails++;}
 printf("WANT=%s\n",want);
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("FACE PICKER v1.24.32 HARNESS: PASS\n");return 0;}
