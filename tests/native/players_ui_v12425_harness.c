/* v1.24.25: two-row filters, Next Role column, status dots, roles wrap, collapsible sections. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static RECT cr={0,0,1600,900};
BOOL __stdcall GetClientRect(HWND h,RECT*r){*r=cr;return 1;}
int main(){int fails=0;RECT r=cr;int xs[12],ws[12];
 for(int W=1280;W<=2560;W+=320){r.right=W;filter_layout(&r,xs,ws);
  for(int i=0;i<12;i++)for(int j=i+1;j<12;j++)if(g_fy[i]==g_fy[j]&&xs[i]<xs[j]+ws[j]&&xs[j]<xs[i]+ws[i]){printf("W=%d filters %d/%d overlap\n",W,i,j);fails++;}
  for(int i=0;i<12;i++)if(xs[i]+ws[i]>W-34+1){printf("W=%d filter %d off screen\n",W,i);fails++;}
  if(W>=1600){const char*longest[10]={"MY CLUB","ALL POSITIONS","AT LIFETIME PLAYSTYLE CAP","ANY PLAYSTYLE","ANY ROLE","OVR 80+","POT 90+","AGE 31+","ANY PLAYSTYLE COUNT","NOT PLAYSTYLE+ ELIGIBLE"};
   for(int i=0;i<10;i++)if(slen(longest[i])*8+20>ws[i]){printf("W=%d filter %d too narrow (%d) for %s\n",W,i,ws[i],longest[i]);fails++;}}}
 /* popups wide enough for their longest option */
 r.right=1600;g_filter_popup=2;{int px,py,pw,rows,cols;popup_geometry(&r,&px,&py,&pw,&rows,&cols);if(pw<slen("At lifetime PlayStyle cap")*8+20){printf("status popup %d\n",pw);fails++;}}
 g_filter_popup=9;{int px,py,pw,rows,cols;popup_geometry(&r,&px,&py,&pw,&rows,&cols);if(pw<slen("Not PlayStyle+ eligible")*8+20){printf("plus popup %d\n",pw);fails++;}}
 g_filter_popup=0;
 /* clicking a row-2 filter opens the right popup */
 g_overlay=(HWND)1;filter_layout(&r,xs,ws);list_filter_click(xs[8]+5,g_fy[8]+10,1);if(g_filter_popup!=8){printf("row2 click popup=%d\n",g_filter_popup);fails++;}
 list_filter_click(xs[2]+5,g_fy[2]+10,1);if(g_filter_popup!=2){printf("row1 click popup=%d\n",g_filter_popup);fails++;}
 g_filter_popup=0;
 /* fifteen columns (v1.24.27: status column removed) */
 g_cols_init=0;ensure_cols(1532);int sum=0;for(int i=0;i<15;i++)sum+=g_colw[i];if(sum!=1532){printf("col sum %d\n",sum);fails++;}
 /* roles wrap grows the row */
 Player a;for(unsigned z=0;z<sizeof(Player);z++)((BYTE*)&a)[z]=0;scpy(a.owned,"Rapid",sizeof(a.owned));
 int h1=player_row_h(&a);scpy(a.roles,"Inside Forward+, Wide Playmaker+, Winger+, False Winger+, Box Crasher+",sizeof(a.roles));int h2=player_row_h(&a);
 if(!(h1==80&&h2>80)){printf("roles row %d -> %d\n",h1,h2);fails++;}
 if(ps_layout(NULL," Winger+",0,0,400,0)!=1){printf("leading space\n");fails++;}
 /* status flags parsed and coloured */
 char line[]="7|Name|ST||17|60|80|2|5|Rapid|50|Finesse Shot|20|Poacher|40|PlayStyle: Developing|Rapid,Technical||1|1|Poacher+|d|100|180|0|0|0|CLUB|50|20|01/01/2009|Ireland|1|13|1|4";
 Player b;for(unsigned z=0;z<sizeof(Player);z++)((BYTE*)&b)[z]=0;parse_player_into(&b,line);
 if(!seq(b.role,"Poacher")||b.club[0]){printf("parse role=%s club=%s\n",b.role,b.club);fails++;}
 /* collapsible sections: header click toggles; pinned bar collapses and scrolls to the header */
 g_sec_y[0]=400;g_sec_h[0]=600;g_sec_abs[0]=400;g_sec_y[1]=1010;g_sec_h[1]=300;g_sec_y[2]=1320;g_sec_h[2]=300;g_sticky_k=-1;g_detail_scroll=0;
 development_path_click(&b,100,410);if(!g_dev_collapsed[0]){printf("header collapse\n");fails++;}
 development_path_click(&b,100,410);if(g_dev_collapsed[0]){printf("header expand\n");fails++;}
 g_detail_scroll=300;g_sec_y[0]=100;g_sec_abs[0]=400;g_sticky_k=0;
 development_path_click(&b,100,330);if(!g_dev_collapsed[0]||g_detail_scroll!=74){printf("sticky collapse=%d scroll=%d\n",g_dev_collapsed[0],g_detail_scroll);fails++;}
 lane_chips(NULL,"PlayStyle: Ready — Queued for acquisition | PlayStyle+: Developing | Role++: Developing",52,100,600);
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("PLAYERS UI v1.24.25 HARNESS: PASS\n");return 0;}
