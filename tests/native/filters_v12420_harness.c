/* v1.24.20: multi-select filter popups stage selections immediately (no own apply). */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
int main(){int fails=0;
 g_ps_option_count=2;scpy(g_ps_options[0],"Rapid",64);scpy(g_ps_options[1],"Technical",64);
 scpy(g_filter_playstyle,"Any PlayStyle",256);scpy(g_pending_playstyle,g_filter_playstyle,256);
 g_filter_popup=3;g_filter_edit_dirty=0;
 apply_popup_choice(1);   /* Rapid */
 if(g_filter_popup!=3){printf("popup closed after a pick\n");fails++;}
 if(!g_filter_edit_dirty||!seq(g_filter_playstyle,"Rapid")){printf("not staged: %s dirty=%d\n",g_filter_playstyle,g_filter_edit_dirty);fails++;}
 apply_popup_choice(2);   /* Technical */
 if(!seq(g_filter_playstyle,"Rapid,Technical")&&!seq(g_filter_playstyle,"Technical,Rapid")){printf("multi not staged: %s\n",g_filter_playstyle);fails++;}
 /* status options and labels */
 if(popup_count()!=4){} g_filter_popup=2; if(popup_count()!=6||!seq(popup_label(3),"Developing a Role++")||!seq(popup_label(4),"At lifetime PlayStyle cap")||!seq(popup_label(5),"Declining")){printf("status options\n");fails++;}
 if(state_index("At lifetime cap")!=4||plus_filter_index("Eligible")!=1||!seq(PLUS_FILTERS[0],"Any PlayStyle+ Status")){printf("legacy mapping\n");fails++;}
 g_filter_popup=8; if(!seq(popup_label(0),"Any PlayStyle Count")){printf("ps count label\n");fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("FILTERS v1.24.20 HARNESS: PASS\n");return 0;}
