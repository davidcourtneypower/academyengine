/* v1.24.29: OVR/POT multi-select, collapsible settings sections, paging, bar colours. */
#define __stdcall
#define DllMain DllMain_unused
#include "overlay_llp64.c"
#include <stdio.h>
BOOL __stdcall InvalidateRect(HWND h,const RECT*r,BOOL e){return 1;}
static RECT cr={0,0,1600,900};
BOOL __stdcall GetClientRect(HWND h,RECT*r){*r=cr;return 1;}
static char sent[4096];int __stdcall fake_unused(void){return 0;}
int main(){int fails=0;g_overlay=(HWND)1;
 /* OVR multi-select */
 begin_filter_popup(5);apply_popup_choice(2);apply_popup_choice(3);
 if(!csv_has(g_filter_ovr,"60-64")||!csv_has(g_filter_ovr,"65-69")||g_filter_popup!=5){printf("ovr multi %s\n",g_filter_ovr);fails++;}
 char lab[192];range_caption(lab,192,g_filter_ovr,"Any OVR","OVR");if(!seq(lab,"OVR (2 ranges)")){printf("caption %s\n",lab);fails++;}
 apply_popup_choice(2);range_caption(lab,192,g_filter_ovr,"Any OVR","OVR");if(!seq(lab,"OVR 65-69")){printf("caption1 %s\n",lab);fails++;}
 begin_filter_popup(6);apply_popup_choice(5);if(!seq(g_filter_pot,"90+")){printf("pot %s\n",g_filter_pot);fails++;}
 reset_player_filters();if(!seq(g_filter_ovr,"Any OVR")||!seq(g_filter_pot,"Any POT")){printf("reset\n");fails++;}
 char k[]="FILTER_OVR_RANGES",v[]="70-74,80+";g_filter_edit_dirty=0;setkv(k,v);if(!seq(g_filter_ovr,"70-74,80+")){printf("setkv %s\n",g_filter_ovr);fails++;}
 /* settings sections collapse */
 g_group_count=2;scpy(g_groups[0].id,"development",32);scpy(g_groups[1].id,"debug",32);
 int h0=settings_total_height();g_group_collapsed[0]=1;int h1=settings_total_height();g_group_collapsed[0]=0;
 g_setting_count=3;scpy(g_settings[0].group,"development",32);scpy(g_settings[1].group,"development",32);scpy(g_settings[2].group,"debug",32);
 h0=settings_total_height();g_group_collapsed[0]=1;h1=settings_total_height();
 if(h0-h1!=2*122){printf("collapse height %d -> %d\n",h0,h1);fails++;}
 if(group_color("development")==group_color("throughput")||group_color("debug")==group_color("generation")||group_color("appearance")==group_color("development")){printf("colours\n");fails++;}
 /* bars: no blue band */
 if(pctcol(60)==C_INFO){printf("blue bar\n");fails++;}
 if(fails){printf("FAIL %d\n",fails);return 1;}
 printf("SETTINGS/FILTERS v1.24.29 HARNESS: PASS\n");return 0;}
