/* v1.24.21: PlayStyles shown by name, rows grow to fit; Health tab removed. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static int drawn=0; static char last[96];
int main(){int fails=0;
 ensure_cols(1600);
 int w=g_colw[6];
 if(ps_layout(NULL,"",0,0,w,0)!=0){printf("empty lines\n");fails++;}
 if(ps_layout(NULL,"Rapid",0,0,w,0)!=1){printf("one name\n");fails++;}
 const char*seven="Finesse Shot,Incisive Pass,Long Ball Pass,Press Proven,Precision Header,Aerial Fortress,Low Driven Shot";
 int L=ps_layout(NULL,seven,0,0,w,0);
 if(L<3){printf("seven names should wrap: %d lines in %dpx\n",L,w);fails++;}
 /* every line fits the column using the same width estimate */
 Player a,b,c; for(unsigned z=0;z<sizeof(Player);z++){((BYTE*)&a)[z]=0;((BYTE*)&b)[z]=0;((BYTE*)&c)[z]=0;}
 scpy(a.owned,"Rapid",sizeof(a.owned)); scpy(b.owned,seven,sizeof(b.owned));
 int ha=player_row_h(&a),hb=player_row_h(&b);
 if(ha!=80){printf("short row %d\n",ha);fails++;}
 if(hb<=80||hb<20+L*18+22){printf("tall row %d for %d lines\n",hb,L);fails++;}
 /* hit test walks variable heights */
 g_player_count=3;g_players[0]=a;g_players[0].id=1;g_players[1]=b;g_players[1].id=2;g_players[2]=a;g_players[2].id=3;g_scroll=0;
 int top=332,bottom=332+2000;
 if(player_row_at(top+10,top,bottom)!=0){printf("row0\n");fails++;}
 if(player_row_at(top+ha+2+hb-5,top,bottom)!=1){printf("row1 bottom\n");fails++;}
 if(player_row_at(top+ha+2+hb+2+5,top,bottom)!=2){printf("row2\n");fails++;}
 if(player_row_at(top+ha+2+hb+2+ha+2+5,top,bottom)!=-1){printf("past end\n");fails++;}
 /* a row that does not fit the visible area is not clickable */
 if(player_row_at(top+ha+2+5,top,top+ha+2+40)!=-1){printf("clipped row clickable\n");fails++;}
 /* tabs: Dashboard, Players, Events, Settings (Health removed) */
 g_overlay=(HWND)1; g_tab=3; pad_tab(1); if(g_tab!=0){printf("tab wrap %d\n",g_tab);fails++;}
 g_tab=0; pad_tab(-1); if(g_tab!=3){printf("tab back wrap %d\n",g_tab);fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("NAMES/ROWS v1.24.21 HARNESS: PASS (7 PlayStyles -> %d lines, row %dpx)\n",L,hb);return 0;}
