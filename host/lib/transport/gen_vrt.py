#!/usr/bin/env python
#
# Copyright 2010 Ettus Research LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
The vrt packer/unpacker code generator:

This script will generate the pack and unpack routines that convert
metatdata into vrt headers and vrt headers into metadata.

The generated code infers jump tables to speed-up the parsing time.
"""

TMPL_TEXT = """
#import time

########################################################################
## setup predicates
########################################################################
#set $sid_p = 0b00001
#set $cid_p = 0b00010
#set $tsi_p = 0b00100
#set $tsf_p = 0b01000
#set $tlr_p = 0b10000

/***********************************************************************
 * This file was generated by $file on $time.strftime("%c")
 **********************************************************************/

\#include <uhd/transport/vrt.hpp>
\#include <boost/asio.hpp> //endianness conversion
\#include <stdexcept>

using namespace uhd;
using namespace uhd::transport;

void vrt::pack(
    const tx_metadata_t &metadata, //input
    boost::uint32_t *header_buff,  //output
    size_t &num_header_words32,    //output
    size_t num_payload_words32,    //input
    size_t &num_packet_words32,    //output
    size_t packet_count,           //input
    double tick_rate               //input
){
    boost::uint32_t vrt_hdr_flags;

    boost::uint8_t pred = 0;
    if (metadata.has_stream_id) pred |= $hex($sid_p);
    if (metadata.has_time_spec) pred |= $hex($tsi_p | $tsf_p);

    switch(pred){
    #for $pred in range(2**5)
    case $pred:
        #set $num_header_words = 1
        #set $flags = 0
        ########## Stream ID ##########
        #if $pred & $sid_p
            header_buff[$num_header_words] = htonl(metadata.stream_id);
            #set $num_header_words += 1
            #set $flags |= (0x1 << 28);
        #end if
        ########## Class ID ##########
        #if $pred & $cid_p
            header_buff[$num_header_words] = htonl(0);
            #set $num_header_words += 1
            header_buff[$num_header_words] = htonl(0);
            #set $num_header_words += 1
            #set $flags |= (0x1 << 27);
        #end if
        ########## Integer Time ##########
        #if $pred & $tsi_p
            header_buff[$num_header_words] = htonl(metadata.time_spec.secs);
            #set $num_header_words += 1
            #set $flags |= (0x3 << 22);
        #end if
        ########## Fractional Time ##########
        #if $pred & $tsf_p
            header_buff[$num_header_words] = htonl(0);
            #set $num_header_words += 1
            header_buff[$num_header_words] = htonl(metadata.time_spec.get_ticks(tick_rate));
            #set $num_header_words += 1
            #set $flags |= (0x1 << 20);
        #end if
        ########## Trailer ##########
        #if $pred & $tlr_p
            #set $flags |= (0x1 << 26);
            #set $num_trailer_words = 1;
        #else
            #set $num_trailer_words = 0;
        #end if
        ########## Variables ##########
            num_header_words32 = $num_header_words;
            num_packet_words32 = $($num_header_words + $num_trailer_words) + num_payload_words32;
            vrt_hdr_flags = $hex($flags);
        break;
    #end for
    }

    //set the burst flags
    if (metadata.start_of_burst) vrt_hdr_flags |= $hex(0x1 << 25);
    if (metadata.end_of_burst)   vrt_hdr_flags |= $hex(0x1 << 24);

    //fill in complete header word
    header_buff[0] = htonl(vrt_hdr_flags |
        ((packet_count & 0xf) << 16) |
        (num_packet_words32 & 0xffff)
    );
}

void vrt::unpack(
    rx_metadata_t &metadata,            //output
    const boost::uint32_t *header_buff, //input
    size_t &num_header_words32,         //output
    size_t &num_payload_words32,        //output
    size_t num_packet_words32,          //input
    size_t &packet_count,               //output
    double tick_rate                    //input
){
    //clear the metadata
    metadata = rx_metadata_t();

    //extract vrt header
    boost::uint32_t vrt_hdr_word = ntohl(header_buff[0]);
    size_t packet_words32 = vrt_hdr_word & 0xffff;
    packet_count = (vrt_hdr_word >> 16) & 0xf;

    //failure cases
    if (packet_words32 == 0 or num_packet_words32 < packet_words32)
        throw std::runtime_error("bad vrt header or packet fragment");
    if (vrt_hdr_word & (0x7 << 29))
        throw std::runtime_error("unsupported vrt packet type");

    boost::uint8_t pred = 0;
    if(vrt_hdr_word & $hex(0x1 << 28)) pred |= $hex($sid_p);
    if(vrt_hdr_word & $hex(0x1 << 27)) pred |= $hex($cid_p);
    if(vrt_hdr_word & $hex(0x3 << 22)) pred |= $hex($tsi_p);
    if(vrt_hdr_word & $hex(0x3 << 20)) pred |= $hex($tsf_p);
    if(vrt_hdr_word & $hex(0x1 << 26)) pred |= $hex($tlr_p);

    switch(pred){
    #for $pred in range(2**5)
    case $pred:
        #set $set_has_time_spec = False
        #set $num_header_words = 1
        ########## Stream ID ##########
        #if $pred & $sid_p
            metadata.has_stream_id = true;
            metadata.stream_id = ntohl(header_buff[$num_header_words]);
            #set $num_header_words += 1
        #end if
        ########## Class ID ##########
        #if $pred & $cid_p
            #set $num_header_words += 1
            #set $num_header_words += 1
        #end if
        ########## Integer Time ##########
        #if $pred & $tsi_p
            metadata.has_time_spec = true;
            #set $set_has_time_spec = True
            metadata.time_spec.secs = ntohl(header_buff[$num_header_words]);
            #set $num_header_words += 1
        #end if
        ########## Fractional Time ##########
        #if $pred & $tsf_p
            #if not $set_has_time_spec
            metadata.has_time_spec = true;
                #set $set_has_time_spec = True
            #end if
            #set $num_header_words += 1
            metadata.time_spec.set_ticks(ntohl(header_buff[$num_header_words]), tick_rate);
            #set $num_header_words += 1
        #end if
        ########## Trailer ##########
        #if $pred & $tlr_p
            #set $num_trailer_words = 1;
        #else
            #set $num_trailer_words = 0;
        #end if
        ########## Variables ##########
            num_header_words32 = $num_header_words;
            num_payload_words32 = packet_words32 - $($num_header_words + $num_trailer_words);
        break;
    #end for
    }
}
"""

from Cheetah import Template
def parse_str(_tmpl_text, **kwargs): return str(Template.Template(_tmpl_text, kwargs))

if __name__ == '__main__':
    from Cheetah import Template
    print parse_str(TMPL_TEXT, file=__file__)
