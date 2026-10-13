/* v1.24.27: no development-history toggle for paths FC27 gave the player. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static RECT cr={0,0,1600,900};
BOOL __stdcall GetClientRect(HWND h,RECT*r){*r=cr;return 1;}
int main(){int fails=0;
 char a[]="NORMAL|7|Rapid|100.00|100.0|1|Acquired. Already owned in FC27.|0";
 char b[]="NORMAL|7|Technical|100.00|100.0|1|Acquired on 01/08/2026. Developed by Academy Engine.|1";
 char c[]="NORMAL|7|Block|40.00|40.0|0|Developing";            /* older payload without the flag */
 parse_path(a);parse_path(b);parse_path(c);
 if(g_paths[0].hist!=0||g_paths[1].hist!=1||g_paths[2].hist!=1){printf("hist flags %d %d %d\n",g_paths[0].hist,g_paths[1].hist,g_paths[2].hist);fails++;}
 Player p;for(unsigned z=0;z<sizeof(Player);z++)((BYTE*)&p)[z]=0;p.id=7;
 g_path_hit_n=0;g_dev_collapsed[0]=0;
 int end=draw_path_section(NULL,&p,"NORMAL","STANDARD PLAYSTYLE PATHS","x",C_INFO,0,34,400,1500,64);
 if(g_sec_h[0]!=70+80+100+100){printf("section height %d\n",g_sec_h[0]);fails++;}
 if(g_path_hit_n!=2){printf("history toggles registered %d (want 2)\n",g_path_hit_n);fails++;}
 for(int i=0;i<g_path_hit_n;i++)if(g_path_hit_idx[i]==0){printf("FC27 path has a toggle\n");fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("PATHS v1.24.27 HARNESS: PASS\n");return 0;}
